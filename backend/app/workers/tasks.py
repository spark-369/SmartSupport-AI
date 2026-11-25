"""Celery tasks."""

from __future__ import annotations

from typing import Any

from app.workers.celery_app import celery_app


@celery_app.task(
    bind=True,
    name="documents.ingest_document",
    max_retries=3,
    autoretry_for=(Exception,),
    retry_backoff=10,
    retry_jitter=True,
)
def ingest_document(self: Any, document_id: str) -> dict[str, Any]:
    """Extract → chunk → embed → persist one uploaded manual (idempotent)."""
    from app.services.ingestion import run_ingestion  # lazy import avoids circulars

    chunk_count = run_ingestion(document_id)
    return {"document_id": document_id, "chunks": chunk_count}
