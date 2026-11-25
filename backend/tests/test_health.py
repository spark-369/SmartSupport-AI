"""Health endpoint tests."""

from __future__ import annotations

from httpx import AsyncClient


async def test_health_ok(client: AsyncClient, fake_redis):
    response = await client.get("/api/v1/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["components"] == {"database": "ok", "redis": "ok", "ollama": "ok"}


async def test_root_metadata(client: AsyncClient):
    response = await client.get("/")
    assert response.status_code == 200
    assert response.json()["name"] == "SmartSupport AI"
