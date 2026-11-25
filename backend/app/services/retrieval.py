"""Vector retrieval over ``float4[]`` embeddings using NumPy cosine similarity.

The per-product index (chunk ids/contents + normalized matrix) is cached in
Redis as a pickled payload and invalidated whenever ingestion mutates the
product's chunks.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field

import numpy as np
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import cache
from app.core.config import get_settings
from app.core.logging import get_logger
from app.models.chunk import Chunk
from app.models.document import Document

logger = get_logger("retrieval")


@dataclass(frozen=True)
class RetrievedChunk:
    chunk_id: str
    document_name: str
    content: str
    score: float
    page: int | None
    chunk_index: int


@dataclass
class ProductIndex:
    """Normalized embedding matrix + parallel metadata arrays for one product."""

    chunk_ids: list[str] = field(default_factory=list)
    contents: list[str] = field(default_factory=list)
    doc_names: list[str] = field(default_factory=list)
    pages: list[int | None] = field(default_factory=list)
    chunk_indexes: list[int] = field(default_factory=list)
    matrix: np.ndarray | None = None  # shape (n, dim), rows L2-normalized

    def __len__(self) -> int:
        return len(self.chunk_ids)

    def search(self, query_vector: np.ndarray, top_k: int, min_score: float) -> list[RetrievedChunk]:
        """Cosine-similarity top-k (both sides pre-normalized → dot product)."""
        if self.matrix is None or not self.chunk_ids:
            return []
        scores = self.matrix @ query_vector
        order = top_k_indices(scores, top_k)
        results: list[RetrievedChunk] = []
        for idx in order:
            score = float(scores[idx])
            if score < min_score:
                continue
            results.append(
                RetrievedChunk(
                    chunk_id=self.chunk_ids[idx],
                    document_name=self.doc_names[idx],
                    content=self.contents[idx],
                    score=round(score, 4),
                    page=self.pages[idx],
                    chunk_index=self.chunk_indexes[idx],
                )
            )
        return results


# ---------------------------------------------------------------------------
# Pure NumPy helpers (unit-tested)
# ---------------------------------------------------------------------------


def normalize_rows(matrix: np.ndarray) -> np.ndarray:
    """L2-normalize rows; zero rows are left as zeros (score 0 against anything)."""
    matrix = np.asarray(matrix, dtype=np.float32)
    norms = np.linalg.norm(matrix, axis=1, keepdims=True)
    norms[norms == 0.0] = 1.0
    return matrix / norms


def normalize_vector(vector: list[float] | np.ndarray) -> np.ndarray:
    vec = np.asarray(vector, dtype=np.float32)
    norm = float(np.linalg.norm(vec))
    if norm == 0.0:
        return vec
    return vec / np.float32(norm)


def top_k_indices(scores: np.ndarray, k: int) -> list[int]:
    """Indices of the k largest scores, descending. Pure function."""
    scores = np.asarray(scores)
    k = max(0, min(k, scores.shape[0]))
    if k == 0:
        return []
    if k < scores.shape[0]:
        part = np.argpartition(scores, -k)[-k:]
    else:
        part = np.arange(scores.shape[0])
    return [int(i) for i in part[np.argsort(scores[part])[::-1]]]


# ---------------------------------------------------------------------------
# Index loading (Redis-cached) + retrieval
# ---------------------------------------------------------------------------


def index_cache_key(product_id: uuid.UUID | str) -> str:
    return f"rag:index:{product_id}"


def build_index_from_rows(rows) -> ProductIndex:
    """rows: sequence of (chunk_id, content, meta, chunk_index, document_name, embedding)."""
    index = ProductIndex()
    embeddings: list[list[float]] = []
    for chunk_id, content, meta, chunk_index, doc_name, embedding in rows:
        if embedding is None:
            continue
        index.chunk_ids.append(str(chunk_id))
        index.contents.append(content)
        index.doc_names.append(doc_name)
        page = None
        if isinstance(meta, dict):
            page = meta.get("page")
            page = int(page) if isinstance(page, (int, float)) else None
        index.pages.append(page)
        index.chunk_indexes.append(int(chunk_index))
        embeddings.append(embedding)
    if embeddings:
        index.matrix = normalize_rows(np.asarray(embeddings, dtype=np.float32))
    return index


async def load_product_index(session: AsyncSession, product_id: uuid.UUID) -> ProductIndex | None:
    """Load (and cache) the retrieval index for a product; None when no embeddings yet.

    Cache is best-effort: without Redis the index is simply rebuilt per query.
    """
    key = index_cache_key(product_id)
    try:
        cached = await cache.cache_get_pickle(key)
    except Exception:
        cached = None
    if cached is not None:
        return cached

    result = await session.execute(
        select(Chunk.id, Chunk.content, Chunk.meta, Chunk.chunk_index, Document.original_filename, Chunk.embedding)
        .join(Document, Chunk.document_id == Document.id)
        .where(Chunk.product_id == product_id, Chunk.embedding.is_not(None))
        .order_by(Chunk.created_at)
    )
    rows = result.all()
    if not rows:
        return None
    index = build_index_from_rows(rows)
    try:
        await cache.cache_set_pickle(key, index, get_settings().retrieval_index_cache_ttl)
    except Exception:
        pass
    return index


async def retrieve(
    session: AsyncSession,
    product_id: uuid.UUID | None,
    query_vector: list[float],
    *,
    top_k: int | None = None,
    min_score: float | None = None,
) -> list[RetrievedChunk]:
    """Top-k cosine-similarity chunks for a product (or [] when product has no index)."""
    if product_id is None:
        return []
    settings = get_settings()
    index = await load_product_index(session, product_id)
    if index is None:
        return []
    query = normalize_vector(query_vector)
    return index.search(
        query,
        top_k or settings.retrieval_top_k,
        min_score if min_score is not None else settings.retrieval_min_score,
    )


async def invalidate_product_index(product_id: uuid.UUID | str) -> None:
    try:
        await cache.get_redis_binary().delete(index_cache_key(product_id))
    except Exception:
        logger.warning("Could not invalidate retrieval index for %s", product_id)


def invalidate_product_index_sync(product_id: uuid.UUID | str) -> None:
    """Sync variant for Celery tasks (best-effort)."""
    cache.cache_delete_sync(index_cache_key(product_id))
