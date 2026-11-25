"""Extraction + Celery ingestion pipeline tests (fake embeddings, real PG)."""

from __future__ import annotations

import os
import uuid
from pathlib import Path

import pytest
from sqlalchemy import select

from app.core import cache
from app.db.sync_session import SyncSessionFactory
from app.models import Document, DocumentStatus, Product
from app.models.chunk import Chunk
from app.services.ingestion import run_ingestion
from app.services.retrieval import index_cache_key
from app.utils.extraction import EmptyDocumentError, UnsupportedFileFormat, extract_pages

FAKE_DIM = 8


def _fake_embed_batch(self, texts: list[str]) -> list[list[float]]:
    # Deterministic pseudo-embeddings derived from text length.
    return [[(len(t) * (i + 1)) % 7 + 0.1 for i in range(FAKE_DIM)] for t in texts]


@pytest.fixture(autouse=True)
def _fake_embeddings(monkeypatch: pytest.MonkeyPatch):
    from app.services.embedding import EmbeddingService

    monkeypatch.setattr(EmbeddingService, "embed_batch", _fake_embed_batch)


def _make_document(content: bytes, filename: str = "manual.md") -> str:
    """Create a real product + document row and stage the file on disk."""
    upload_dir = Path(os.environ["SMARTSUPPORT_UPLOAD_DIR"])
    dest_dir = upload_dir / "prod-1"
    dest_dir.mkdir(parents=True, exist_ok=True)
    stored = dest_dir / f"{uuid.uuid4().hex}{Path(filename).suffix}"
    stored.write_bytes(content)

    with SyncSessionFactory() as session:
        product = Product(name="Ingestion Probe", slug=f"ingestion-probe-{uuid.uuid4().hex[:8]}")
        session.add(product)
        session.flush()
        document = Document(
            product_id=product.id,
            original_filename=filename,
            stored_path=f"prod-1/{stored.name}",
            file_type=Path(filename).suffix,
            size_bytes=len(content),
            status=DocumentStatus.PENDING,
        )
        session.add(document)
        session.commit()
        return str(document.id)


# ---------------------------------------------------------------------------
# extraction
# ---------------------------------------------------------------------------


def test_extract_txt(tmp_path: Path):
    path = tmp_path / "note.txt"
    path.write_text("hello world", encoding="utf-8")
    pages = extract_pages(path)
    assert pages == [("hello world", {"page": None})]


def test_extract_docx(tmp_path: Path):
    import docx

    path = tmp_path / "manual.docx"
    document = docx.Document()
    document.add_paragraph("Warranty is 24 months.")
    document.save(str(path))
    pages = extract_pages(path)
    assert any("Warranty is 24 months." in text for text, _ in pages)


def test_extract_empty_raises(tmp_path: Path):
    path = tmp_path / "blank.txt"
    path.write_text("   \n  ", encoding="utf-8")
    with pytest.raises(EmptyDocumentError):
        extract_pages(path)


def test_extract_unsupported(tmp_path: Path):
    path = tmp_path / "image.png"
    path.write_bytes(b"\x89PNG")
    with pytest.raises(UnsupportedFileFormat):
        extract_pages(path)


# ---------------------------------------------------------------------------
# ingestion pipeline (sync, idempotent, cache-invalidating)
# ---------------------------------------------------------------------------


def test_run_ingestion_happy_path():
    document_id = _make_document(b"# Manual\n\n" + ("Descale every three months. " * 400).encode())
    count = run_ingestion(document_id)
    assert count > 0

    with SyncSessionFactory() as session:
        document = session.get(Document, uuid.UUID(document_id))
        assert document is not None
        assert document.status is DocumentStatus.READY
        assert document.chunk_count == count
        rows = (
            session.execute(select(Chunk).where(Chunk.document_id == document.id)).scalars().all()
        )
        assert len(rows) == count
        assert all(r.embedding is not None and len(r.embedding) == FAKE_DIM for r in rows)
        assert [r.chunk_index for r in rows] == list(range(count))


def test_run_ingestion_is_idempotent():
    document_id = _make_document(b"# Manual\n\n" + b"content " * 300)
    first = run_ingestion(document_id)
    second = run_ingestion(document_id)  # retry must not duplicate
    assert first == second


def test_run_ingestion_failure_marks_document_failed():
    document_id = _make_document(b"x", "unsupported.exe")
    with pytest.raises(Exception):
        run_ingestion(document_id)
    with SyncSessionFactory() as session:
        document = session.get(Document, uuid.UUID(document_id))
        assert document is not None
        assert document.status is DocumentStatus.FAILED
        assert document.error is not None
