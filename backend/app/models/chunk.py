"""Chunk model — a text segment of a manual with its float4[] embedding.

Embeddings are stored as native PostgreSQL ``real[]`` (float4[]) and similarity
search is computed in NumPy (cosine similarity) — no pgvector extension needed.
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, Any

from sqlalchemy import REAL, ForeignKey, Index, Integer, Text
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.document import Document


class Chunk(Base, TimestampMixin):
    __tablename__ = "chunks"
    __table_args__ = (Index("ix_chunks_product_id", "product_id"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    document_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("documents.id", ondelete="CASCADE"), index=True, nullable=False
    )
    # Denormalized for fast product-wide retrieval scans.
    product_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("products.id", ondelete="CASCADE"), nullable=False
    )
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    # PostgreSQL native float4[] — similarity search runs in NumPy (cosine).
    embedding: Mapped[list[float] | None] = mapped_column(ARRAY(REAL()), nullable=True)
    token_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    meta: Mapped[dict[str, Any]] = mapped_column("meta", JSONB, default=dict, nullable=False)

    document: Mapped["Document"] = relationship(back_populates="chunks")
