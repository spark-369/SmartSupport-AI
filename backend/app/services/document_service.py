"""Document lifecycle: upload to local filesystem, dispatch ingestion, delete/retry."""

from __future__ import annotations

import uuid
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.errors import AppError, ConflictError, NotFoundError
from app.core.logging import get_logger
from app.models.document import Document
from app.models.enums import DocumentStatus
from app.models.product import Product
from app.models.user import User
from app.services.retrieval import invalidate_product_index

logger = get_logger("document_service")

_UPLOAD_CHUNK = 1024 * 1024


def absolute_stored_path(document: Document) -> Path:
    settings = get_settings()
    return settings.upload_dir / document.stored_path


async def list_documents(session: AsyncSession, product_id: uuid.UUID) -> list[Document]:
    result = await session.execute(
        select(Document).where(Document.product_id == product_id).order_by(Document.created_at.desc())
    )
    return list(result.scalars().all())


async def get_document(session: AsyncSession, document_id: uuid.UUID) -> Document | None:
    return await session.get(Document, document_id)


async def get_document_or_404(session: AsyncSession, document_id: uuid.UUID) -> Document:
    document = await get_document(session, document_id)
    if document is None:
        raise NotFoundError("Document not found.")
    return document


async def save_upload(
    session: AsyncSession,
    product: Product,
    uploader: User,
    filename: str,
    content_type: str | None,
    read_chunk,
) -> Document:
    """Stream an upload to disk, create the row and enqueue the ingestion task.

    ``read_chunk`` is an async callable returning the next bytes chunk, keeping
    this function transport-agnostic (UploadFile in the API, stubs in tests).
    """
    settings = get_settings()
    original = Path(filename or "unnamed").name
    ext = Path(original).suffix.lower()

    if ext not in settings.allowed_upload_extensions:
        raise AppError(
            f"Unsupported file type '{ext or '(none)'}'. Allowed: "
            f"{', '.join(sorted(settings.allowed_upload_extensions))}",
            status_code=415,
            code="unsupported_media_type",
        )

    dest_dir = settings.upload_dir / str(product.id)
    dest_dir.mkdir(parents=True, exist_ok=True)
    stored_name = f"{uuid.uuid4().hex}{ext}"
    dest_path = dest_dir / stored_name

    size = 0
    try:
        with dest_path.open("wb") as out:
            while True:
                chunk = await read_chunk(_UPLOAD_CHUNK)
                if not chunk:
                    break
                size += len(chunk)
                if size > settings.max_upload_bytes:
                    raise AppError(
                        f"File exceeds the {settings.max_upload_mb} MB limit.",
                        status_code=413,
                        code="payload_too_large",
                    )
                out.write(chunk)
    except AppError:
        dest_path.unlink(missing_ok=True)
        raise
    except Exception:
        dest_path.unlink(missing_ok=True)
        raise

    document = Document(
        product_id=product.id,
        uploaded_by=uploader.id,
        original_filename=original,
        stored_path=f"{product.id}/{stored_name}",
        file_type=ext,
        size_bytes=size,
        status=DocumentStatus.PENDING,
    )
    session.add(document)
    await session.commit()
    await session.refresh(document)

    from app.workers.tasks import ingest_document

    ingest_document.delay(str(document.id))
    logger.info("Queued ingestion for document=%s (%s bytes)", document.id, size)
    return document


async def delete_document(session: AsyncSession, document: Document) -> None:
    path = absolute_stored_path(document)
    await session.delete(document)
    await session.commit()
    try:
        path.unlink(missing_ok=True)
    except OSError:
        logger.warning("Could not remove file %s", path)
    await invalidate_product_index(document.product_id)


async def retry_document(session: AsyncSession, document: Document) -> Document:
    if document.status != DocumentStatus.FAILED:
        raise ConflictError("Only failed documents can be retried.")
    document.status = DocumentStatus.PENDING
    document.error = None
    await session.commit()
    await session.refresh(document)

    from app.workers.tasks import ingest_document

    ingest_document.delay(str(document.id))
    return document
