"""Text extraction for supported manual formats (PDF / DOCX / TXT / Markdown)."""

from __future__ import annotations

from pathlib import Path
from typing import Any


class UnsupportedFileFormat(Exception):
    """Raised when a file extension has no extractor."""


class EmptyDocumentError(Exception):
    """Raised when extraction yields no usable text."""


def extract_pages(path: Path) -> list[tuple[str, dict[str, Any]]]:
    """Return ``[(text, metadata), ...]`` preserving page boundaries where possible."""
    ext = path.suffix.lower()
    if ext == ".pdf":
        pages = _extract_pdf(path)
    elif ext == ".docx":
        pages = _extract_docx(path)
    elif ext in {".txt", ".md", ".markdown"}:
        pages = _extract_plain(path)
    else:
        raise UnsupportedFileFormat(f"No extractor for '{ext}'")

    if not any(text.strip() for text, _ in pages):
        raise EmptyDocumentError("Document contains no extractable text.")
    return pages


def _extract_pdf(path: Path) -> list[tuple[str, dict[str, Any]]]:
    from pypdf import PdfReader

    reader = PdfReader(str(path))
    pages: list[tuple[str, dict[str, Any]]] = []
    for index, page in enumerate(reader.pages, start=1):
        text = page.extract_text() or ""
        if text.strip():
            pages.append((text, {"page": index}))
    return pages


def _extract_docx(path: Path) -> list[tuple[str, dict[str, Any]]]:
    import docx

    document = docx.Document(str(path))
    lines = [p.text for p in document.paragraphs if p.text.strip()]
    for table in document.tables:
        for row in table.rows:
            cells = [cell.text.strip() for cell in row.cells if cell.text.strip()]
            if cells:
                lines.append(" | ".join(cells))
    return [("\n".join(lines), {"page": None})]


def _extract_plain(path: Path) -> list[tuple[str, dict[str, Any]]]:
    text = path.read_text(encoding="utf-8", errors="replace")
    return [(text, {"page": None})]
