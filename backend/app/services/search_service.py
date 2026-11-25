"""Semantic manual search — embed the query, rank chunks across products.

Reuses the retrieval service (Redis-cached per-product indexes) so search and
chat always agree on scoring. When no product is specified, results from all
products are merged and ranked globally.
"""

from __future__ import annotations

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.schemas.search import SearchResult
from app.services import product_service
from app.services.embedding import EmbeddingService
from app.services.retrieval import retrieve


async def semantic_search(
    session: AsyncSession,
    embedder: EmbeddingService,
    query: str,
    product_id: uuid.UUID | None,
    *,
    top_k: int | None = None,
) -> list[SearchResult]:
    settings = get_settings()
    limit = top_k or settings.retrieval_top_k
    vector = await embedder.embed_query(query)

    if product_id is not None:
        product = await product_service.get_product_or_404(session, product_id)
        chunks = await retrieve(session, product.id, vector, top_k=limit, min_score=settings.retrieval_min_score)
        return [_to_result(chunk, product.id, product.name) for chunk in chunks]

    merged: list[SearchResult] = []
    for product in await product_service.list_products(session):
        chunks = await retrieve(session, product.id, vector, top_k=limit, min_score=settings.retrieval_min_score)
        merged.extend(_to_result(chunk, product.id, product.name) for chunk in chunks)
    merged.sort(key=lambda result: result.score, reverse=True)
    return merged[:limit]


def _to_result(chunk, product_id: uuid.UUID, product_name: str) -> SearchResult:
    return SearchResult(
        chunk_id=chunk.chunk_id,
        product_id=product_id,
        product_name=product_name,
        document_name=chunk.document_name,
        content=chunk.content,
        score=chunk.score,
        page=chunk.page,
    )