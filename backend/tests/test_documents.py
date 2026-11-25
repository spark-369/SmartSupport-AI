"""Document upload/list/delete endpoint tests (Celery task stubbed)."""

from __future__ import annotations

import io

import pytest
from httpx import AsyncClient

from app.core.config import get_settings


async def _create_product(client: AsyncClient, headers: dict[str, str]) -> str:
    response = await client.post(
        "/api/v1/products", json={"name": "Testiclean T1"}, headers=headers
    )
    assert response.status_code == 201
    return response.json()["id"]


async def test_upload_txt_and_list(client: AsyncClient, admin_headers):
    product_id = await _create_product(client, admin_headers)
    response = await client.post(
        f"/api/v1/products/{product_id}/documents",
        files={"file": ("manual.txt", io.BytesIO(b"Hello manual " * 50), "text/plain")},
        headers=admin_headers,
    )
    assert response.status_code == 202, response.text
    document = response.json()
    assert document["status"] == "pending"
    assert document["file_type"] == ".txt"
    assert document["size_bytes"] > 0

    listed = await client.get(
        f"/api/v1/products/{product_id}/documents", headers=admin_headers
    )
    assert [d["id"] for d in listed.json()] == [document["id"]]


async def test_unsupported_extension(client: AsyncClient, admin_headers):
    product_id = await _create_product(client, admin_headers)
    response = await client.post(
        f"/api/v1/products/{product_id}/documents",
        files={"file": ("virus.exe", io.BytesIO(b"MZ"), "application/octet-stream")},
        headers=admin_headers,
    )
    assert response.status_code == 415


async def test_member_cannot_upload(client: AsyncClient, admin_headers, member_headers):
    product_id = await _create_product(client, admin_headers)
    response = await client.post(
        f"/api/v1/products/{product_id}/documents",
        files={"file": ("m.md", io.BytesIO(b"# hi"), "text/markdown")},
        headers=member_headers,
    )
    assert response.status_code == 403


async def test_upload_size_limit(client: AsyncClient, admin_headers, monkeypatch):
    monkeypatch.setattr(get_settings(), "max_upload_mb", 1)
    product_id = await _create_product(client, admin_headers)
    payload = b"x" * (2 * 1024 * 1024)
    response = await client.post(
        f"/api/v1/products/{product_id}/documents",
        files={"file": ("big.txt", io.BytesIO(payload), "text/plain")},
        headers=admin_headers,
    )
    assert response.status_code == 413


async def test_delete_document(client: AsyncClient, admin_headers):
    product_id = await _create_product(client, admin_headers)
    uploaded = await client.post(
        f"/api/v1/products/{product_id}/documents",
        files={"file": ("m.md", io.BytesIO(b"# Manual"), "text/markdown")},
        headers=admin_headers,
    )
    doc_id = uploaded.json()["id"]
    deleted = await client.delete(f"/api/v1/documents/{doc_id}", headers=admin_headers)
    assert deleted.status_code == 204
    gone = await client.get(f"/api/v1/documents/{doc_id}", headers=admin_headers)
    assert gone.status_code == 404


async def test_get_document_requires_auth(client: AsyncClient):
    response = await client.get("/api/v1/documents/00000000-0000-0000-0000-000000000000")
    assert response.status_code == 401


@pytest.mark.parametrize("filename", ["a.md", "b.markdown", "c.txt", "d.docx", "e.pdf"])
async def test_allowed_extensions_accepted(
    client: AsyncClient, admin_headers, filename: str
):
    product_id = await _create_product(client, admin_headers)
    response = await client.post(
        f"/api/v1/products/{product_id}/documents",
        files={"file": (filename, io.BytesIO(b"data"), "application/octet-stream")},
        headers=admin_headers,
    )
    assert response.status_code == 202, response.text


async def test_download_original_file(client: AsyncClient, admin_headers, member_headers):
    product_id = await _create_product(client, admin_headers)
    uploaded = await client.post(
        f"/api/v1/products/{product_id}/documents",
        files={"file": ("manual.md", io.BytesIO(b"# Manual body"), "text/markdown")},
        headers=admin_headers,
    )
    doc_id = uploaded.json()["id"]

    response = await client.get(f"/api/v1/documents/{doc_id}/file", headers=admin_headers)
    assert response.status_code == 200, response.text
    assert response.content == b"# Manual body"
    assert "manual.md" in response.headers.get("content-disposition", "")

    # Members cannot download stored manuals.
    forbidden = await client.get(
        f"/api/v1/documents/{doc_id}/file", headers=member_headers
    )
    assert forbidden.status_code == 403

    missing = await client.get(
        "/api/v1/documents/00000000-0000-0000-0000-000000000000/file",
        headers=admin_headers,
    )
    assert missing.status_code == 404
