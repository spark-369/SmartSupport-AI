"""Synchronous ingestion pipeline executed by the Celery worker.

Flow: mark processing → extract text per page → chunk (LangChain splitter) →
embed in batches (Ollama) → persist chunks with float4[] embeddings → mark ready
→ invalidate the product's retrieval index cache.

The task is idempotent: existing chunks for the document are removed before
inserting, so retries never duplicate data.
"""

from __future__ import annotations

import uuid
from functools import lru_cache

from langchain_text_splitters import RecursiveCharacterTextSplitter
from sqlalchemy import delete

from app.core.config import get_settings
from app.core.logging import get_logger
from app.db.sync_session import sync_session_scope
from app.models.chunk import Chunk
from app.models.document import Document
from app.models.enums import DocumentStatus
from app.services.document_service import absolute_stored_path
from app.services.embedding import get_embedding_service
from app.services.retrieval import invalidate_product_index_sync
from app.utils.extraction import extract_pages

logger = get_logger("ingestion")


@lru_cache
def get_splitter() -> RecursiveCharacterTextSplitter:
    settings = get_settings()
    return RecursiveCharacterTextSplitter(
        chunk_size=settings.chunk_size,
        chunk_overlap=settings.chunk_overlap,
        length_function=len,
        add_start_index=True,
    )


def run_ingestion(document_id: str) -> int:
    """Ingest one document; returns the number of chunks stored."""
    doc_uuid = uuid.UUID(document_id)
    settings = get_settings()

    with sync_session_scope() as session:
        document = session.get(Document, doc_uuid)
        if document is None:
            logger.error("Ingestion for unknown document %s", document_id)
            return 0
        product_id = document.product_id

        document.status = DocumentStatus.PROCESSING
        document.error = None
        session.commit()

        try:
            path = absolute_stored_path(document)
            pages = extract_pages(path)

            # Idempotency: clear any chunks from a previous attempt.
            session.execute(delete(Chunk).where(Chunk.document_id == document.id))
            session.commit()

            splitter = get_splitter()
            embedder = get_embedding_service()
            chunk_index = 0
            for page_text, meta in pages:
                pieces = splitter.split_text(page_text)
                if not pieces:
                    continue
                vectors = embedder.embed_batch(pieces)
                for piece, vector in zip(pieces, vectors, strict=True):
                    session.add(
                        Chunk(
                            document_id=document.id,
                            product_id=product_id,
                            chunk_index=chunk_index,
                            content=piece,
                            embedding=vector,
                            token_count=max(1, len(piece) // 4),
                            meta={**(meta or {}), "chunk_index": chunk_index},
                        )
                    )
                    chunk_index += 1
                session.commit()

            document.status = DocumentStatus.READY
            document.chunk_count = chunk_index
            document.error = None
            session.commit()

        except Exception as exc:
            session.rollback()
            document = session.get(Document, doc_uuid)
            if document is not None:
                document.status = DocumentStatus.FAILED
                document.error = f"{exc.__class__.__name__}: {exc}"[:2000]
                session.commit()
            logger.exception("Ingestion failed for document %s", document_id)
            raise

    invalidate_product_index_sync(product_id)
    logger.info("Ingested document %s → %d chunks", document_id, chunk_index)
    return chunk_index
