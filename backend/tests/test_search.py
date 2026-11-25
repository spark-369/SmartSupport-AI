"""Semantic search endpoint tests (fake embedder + fake retrieval)."""

from __future__ import annotations

import uuid

import pytest
from httpx import AsyncClient

from app.api.deps import get_embedder
from app.services.retrieval import RetrievedChunk
from tests.test_pipeline import FakeEmbedder


def _chunk(chunk_id: str, content: str, score: float) -> RetrievedChunk:
    return RetrievedChunk(
        chunk_id=chunk_id,
        document_name="manual.md",
        content=content,
        score=score,
        page=3,
        chunk_index=0,
    )


def _patch_retrieve(monkeypatch: pytest.MonkeyPatch, per_product: dict[str, list[RetrievedChunk]]) -> None:
    async def fake_retrieve(session, product_id, vector, *, top_k=None, min_score=None):
        return list(per_product.get(str(product_id), []))[: top_k or 6]

    monkeypatch.setattr("app.services.search_service.retrieve", fake_retrieve)


async def _create_product(client: AsyncClient, headers: dict[str, str], name: str) -> str:
    response = await client.post("/api/v1/products", json={"name": name}, headers=headers)
    assert response.status_code == 201
    return response.json()["id"]


async def test_search_single_product(
    client: AsyncClient, app, admin_headers, monkeypatch: pytest.MonkeyPatch
):
    app.dependency_overrides[get_embedder] = lambda: FakeEmbedder()
    product_a = await _create_product(client, admin_headers, "Searchable A")
    product_b = await _create_product(client, admin_headers, "Searchable B")
    _patch_retrieve(
        monkeypatch,
        {
            product_a: [_chunk("a1", "Descale instructions", 0.90), _chunk("a2", "Warranty terms", 0.80)],
            product_b: [_chunk("b1", "Steam wand care", 0.95)],
        },
    )

    response = await client.post(
        "/api/v1/search",
        json={"query": "descale", "product_id": product_a},
        headers=admin_headers,
    )
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["query"] == "descale"
    assert data["total"] == 2
    assert [r["chunk_id"] for r in data["results"]] == ["a1", "a2"]  # score-desc within product
    assert data["results"][0]["product_id"] == product_a
    assert data["results"][0]["page"] == 3


async def test_search_across_products_merges_by_score(
    client: AsyncClient, app, admin_headers, monkeypatch: pytest.MonkeyPatch
):
    app.dependency_overrides[get_embedder] = lambda: FakeEmbedder()
    product_a = await _create_product(client, admin_headers, "Merged A")
    product_b = await _create_product(client, admin_headers, "Merged B")
    _patch_retrieve(
        monkeypatch,
        {
            product_a: [_chunk("a1", "A content", 0.90)],
            product_b: [_chunk("b1", "B content", 0.95)],
        },
    )

    response = await client.post("/api/v1/search", json={"query": "anything"}, headers=admin_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 2
    assert [r["chunk_id"] for r in data["results"]] == ["b1", "a1"]  # global ranking
    assert {r["product_name"] for r in data["results"]} == {"Merged A", "Merged B"}


async def test_search_requires_auth_and_valid_query(client: AsyncClient, admin_headers):
    anonymous = await client.post("/api/v1/search", json={"query": "descale"})
    assert anonymous.status_code == 401

    too_short = await client.post("/api/v1/search", json={"query": "d"}, headers=admin_headers)
    assert too_short.status_code == 422

    missing = await client.post("/api/v1/search", json={}, headers=admin_headers)
    assert missing.status_code == 422


async def test_search_unknown_product_404(client: AsyncClient, app, admin_headers, monkeypatch: pytest.MonkeyPatch):
    app.dependency_overrides[get_embedder] = lambda: FakeEmbedder()
    _patch_retrieve(monkeypatch, {})
    response = await client.post(
        "/api/v1/search",
        json={"query": "descale", "product_id": str(uuid.uuid4())},
        headers=admin_headers,
    )
    assert response.status_code == 404