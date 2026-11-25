"""Semantic manual search endpoint."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.deps import CurrentUser, DbSession, EmbedderDep, user_rate_limit
from app.core.config import get_settings
from app.schemas.search import SearchRequest, SearchResponse
from app.services import search_service

router = APIRouter(prefix="/search", tags=["search"])

_search_limit = user_rate_limit("search", get_settings().rate_limit_search_per_minute, 60)


@router.post("", response_model=SearchResponse)
async def search_manuals(
    payload: SearchRequest,
    user: CurrentUser,
    db: DbSession,
    embedder: EmbedderDep,
    _rate: None = Depends(_search_limit),
) -> SearchResponse:
    """Embed the query and rank manual chunks across one or all products."""
    results = await search_service.semantic_search(db, embedder, payload.query, payload.product_id)
    return SearchResponse(query=payload.query, total=len(results), results=results)