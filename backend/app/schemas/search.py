"""Search schemas (semantic manual search)."""

from __future__ import annotations

import uuid

from pydantic import BaseModel, Field


class SearchRequest(BaseModel):
    query: str = Field(min_length=2, max_length=400)
    product_id: uuid.UUID | None = None


class SearchResult(BaseModel):
    chunk_id: str
    product_id: uuid.UUID
    product_name: str
    document_name: str
    content: str
    score: float
    page: int | None = None


class SearchResponse(BaseModel):
    query: str
    total: int
    results: list[SearchResult]