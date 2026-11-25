"""Product CRUD + RBAC tests."""

from __future__ import annotations

import io

from httpx import AsyncClient

PRODUCT = {"name": "Aurora Kettle K2", "description": "1.7 L kettle", "version": "1.0"}


async def _create_product(client: AsyncClient, headers: dict[str, str]) -> dict:
    response = await client.post("/api/v1/products", json=PRODUCT, headers=headers)
    assert response.status_code == 201, response.text
    return response.json()


async def test_admin_can_create_and_slug_is_generated(client: AsyncClient, admin_headers):
    product = await _create_product(client, admin_headers)
    assert product["slug"] == "aurora-kettle-k2"
    assert product["document_count"] == 0


async def test_member_cannot_create(client: AsyncClient, member_headers):
    response = await client.post("/api/v1/products", json=PRODUCT, headers=member_headers)
    assert response.status_code == 403


async def test_slug_collision_gets_suffix(client: AsyncClient, admin_headers):
    first = await _create_product(client, admin_headers)
    second = await _create_product(client, admin_headers)
    assert first["slug"] == "aurora-kettle-k2"
    assert second["slug"] == "aurora-kettle-k2-2"


async def test_list_and_get(client: AsyncClient, admin_headers, member_headers):
    product = await _create_product(client, admin_headers)
    listed = await client.get("/api/v1/products", headers=member_headers)
    assert listed.status_code == 200
    assert [p["id"] for p in listed.json()] == [product["id"]]

    fetched = await client.get(f"/api/v1/products/{product['id']}", headers=member_headers)
    assert fetched.status_code == 200


async def test_update_and_delete(client: AsyncClient, admin_headers):
    product = await _create_product(client, admin_headers)
    patched = await client.patch(
        f"/api/v1/products/{product['id']}", json={"version": "1.1"}, headers=admin_headers
    )
    assert patched.status_code == 200
    assert patched.json()["version"] == "1.1"

    deleted = await client.delete(f"/api/v1/products/{product['id']}", headers=admin_headers)
    assert deleted.status_code == 204
    missing = await client.get(f"/api/v1/products/{product['id']}", headers=admin_headers)
    assert missing.status_code == 404


async def test_invalid_slug_rejected(client: AsyncClient, admin_headers):
    response = await client.post(
        "/api/v1/products", json={**PRODUCT, "slug": "Bad Slug!"}, headers=admin_headers
    )
    assert response.status_code == 422


async def test_product_stats_in_list_and_detail(client: AsyncClient, admin_headers):
    product = await _create_product(client, admin_headers)
    for filename, body in (("a.md", b"# a"), ("b.txt", b"b")):
        uploaded = await client.post(
            f"/api/v1/products/{product['id']}/documents",
            files={"file": (filename, io.BytesIO(body), "text/plain")},
            headers=admin_headers,
        )
        assert uploaded.status_code == 202

    listed = (await client.get("/api/v1/products", headers=admin_headers)).json()[0]
    assert listed["document_count"] == 2
    assert listed["pending_count"] == 2  # celery is stubbed → stays pending
    assert listed["ready_count"] == 0
    assert listed["processing_count"] == 0
    assert listed["failed_count"] == 0
    assert listed["total_chunks"] == 0

    detail = await client.get(f"/api/v1/products/{product['id']}", headers=admin_headers)
    assert detail.status_code == 200
    assert detail.json()["document_count"] == 2
    assert detail.json()["pending_count"] == 2


async def test_renamed_product_updates_conversation_snapshot(
    client: AsyncClient, admin_headers
):
    product = await _create_product(client, admin_headers)
    conversation = await client.post(
        "/api/v1/conversations", json={"product_id": product["id"]}, headers=admin_headers
    )
    assert conversation.status_code == 201

    patched = await client.patch(
        f"/api/v1/products/{product['id']}",
        json={"name": "Renamed R9"},
        headers=admin_headers,
    )
    assert patched.status_code == 200
    assert patched.json()["name"] == "Renamed R9"

    conversations = (await client.get("/api/v1/conversations", headers=admin_headers)).json()
    assert conversations[0]["product_name"] == "Renamed R9"
