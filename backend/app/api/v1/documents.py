"""Document endpoints: upload, list, inspect, delete, retry failed ingestion."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, File, Response, UploadFile, status
from fastapi.responses import FileResponse

from app.api.deps import AdminUser, CurrentUser, DbSession, user_rate_limit
from app.core.config import get_settings
from app.core.errors import NotFoundError
from app.schemas.document import DocumentPublic
from app.services import document_service, product_service

router = APIRouter(tags=["documents"])

_upload_limit = user_rate_limit(
    "upload", get_settings().rate_limit_upload_per_hour, 3600
)

_MEDIA_TYPES = {
    ".pdf": "application/pdf",
    ".md": "text/markdown",
    ".markdown": "text/markdown",
    ".txt": "text/plain",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
}


@router.post(
    "/products/{product_id}/documents",
    response_model=DocumentPublic,
    status_code=status.HTTP_202_ACCEPTED,
)
async def upload_document(
    product_id: uuid.UUID,
    db: DbSession,
    admin: AdminUser,
    file: UploadFile = File(...),
    _: None = Depends(_upload_limit),
) -> DocumentPublic:
    """Upload a manual (PDF/MD/TXT/DOCX). Ingestion runs asynchronously in Celery."""
    product = await product_service.get_product_or_404(db, product_id)

    async def read_chunk(size: int) -> bytes:
        return await file.read(size)

    document = await document_service.save_upload(
        db, product, admin, file.filename or "unnamed", file.content_type, read_chunk
    )
    return DocumentPublic.model_validate(document)


@router.get("/products/{product_id}/documents", response_model=list[DocumentPublic])
async def list_documents(
    product_id: uuid.UUID,
    _: CurrentUser,
    db: DbSession,
) -> list[DocumentPublic]:
    await product_service.get_product_or_404(db, product_id)
    documents = await document_service.list_documents(db, product_id)
    return [DocumentPublic.model_validate(d) for d in documents]


@router.get("/documents/{document_id}", response_model=DocumentPublic)
async def get_document(document_id: uuid.UUID, _: CurrentUser, db: DbSession) -> DocumentPublic:
    document = await document_service.get_document_or_404(db, document_id)
    return DocumentPublic.model_validate(document)


@router.delete("/documents/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_document(document_id: uuid.UUID, db: DbSession, _: AdminUser) -> Response:
    document = await document_service.get_document_or_404(db, document_id)
    await document_service.delete_document(db, document)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/documents/{document_id}/retry", response_model=DocumentPublic)
async def retry_document(document_id: uuid.UUID, db: DbSession, _: AdminUser) -> DocumentPublic:
    document = await document_service.get_document_or_404(db, document_id)
    retried = await document_service.retry_document(db, document)
    return DocumentPublic.model_validate(retried)


@router.get("/documents/{document_id}/file")
async def download_document(document_id: uuid.UUID, db: DbSession, _: AdminUser) -> FileResponse:
    """Download the original uploaded manual (admin only)."""
    document = await document_service.get_document_or_404(db, document_id)
    path = document_service.absolute_stored_path(document)
    if not path.is_file():
        raise NotFoundError("The stored file is missing on disk.")
    return FileResponse(
        path,
        media_type=_MEDIA_TYPES.get(document.file_type, "application/octet-stream"),
        filename=document.original_filename,
    )
