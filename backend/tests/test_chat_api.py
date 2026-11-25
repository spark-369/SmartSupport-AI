"""SSE chat endpoint tests with fake RAG dependencies."""

from __future__ import annotations

import json
import uuid

from httpx import AsyncClient

from app.api.deps import get_embedder, get_rag
from tests.test_pipeline import FakeEmbedder, FakeRAG


async def _setup_product_and_conversation(client: AsyncClient, headers: dict[str, str]) -> str:
    product = await client.post(
        "/api/v1/products", json={"name": "Chat Probe"}, headers=headers
    )
    conversation = await client.post(
        "/api/v1/conversations", json={"product_id": product.json()["id"]}, headers=headers
    )
    return conversation.json()["id"]


def _parse_sse(text: str) -> dict[str, list[dict]]:
    events: dict[str, list[dict]] = {}
    for block in text.split("\n\n"):
        if not block.strip():
            continue
        lines = block.strip().splitlines()
        event_type = next(line[7:] for line in lines if line.startswith("event: "))
        data_line = next(line[6:] for line in lines if line.startswith("data: "))
        events.setdefault(event_type, []).append(json.loads(data_line))
    return events


async def test_stream_message_full_event_flow(
    client: AsyncClient, app, admin_headers, fake_redis
):
    app.dependency_overrides[get_rag] = lambda: FakeRAG()
    app.dependency_overrides[get_embedder] = lambda: FakeEmbedder()

    conversation_id = await _setup_product_and_conversation(client, admin_headers)
    response = await client.post(
        f"/api/v1/conversations/{conversation_id}/messages/stream",
        json={"content": "What is in the box?"},
        headers=admin_headers,
    )
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")

    events = _parse_sse(response.text)
    assert set(events) == {"status", "sources", "token", "answer", "done"}
    assert events["answer"][0]["message"]["role"] == "assistant"
    # Streamed deltas reconstruct the answer prose.
    streamed = "".join(frame["delta"] for frame in events["token"])
    assert streamed and streamed in events["answer"][0]["message"]["content"]

    # Both the user and assistant messages were persisted.
    detail = await client.get(f"/api/v1/conversations/{conversation_id}", headers=admin_headers)
    roles = [m["role"] for m in detail.json()["messages"]]
    assert roles == ["user", "assistant"]
    assert detail.json()["title"] != "New conversation"  # title was generated


async def test_stream_on_foreign_conversation_is_404(
    client: AsyncClient, admin_headers, member_headers
):
    conversation_id = await _setup_product_and_conversation(client, admin_headers)
    response = await client.post(
        f"/api/v1/conversations/{conversation_id}/messages/stream",
        json={"content": "hi"},
        headers=member_headers,
    )
    assert response.status_code == 404


async def test_conversation_crud(client: AsyncClient, admin_headers):
    conversation_id = await _setup_product_and_conversation(client, admin_headers)
    listed = await client.get("/api/v1/conversations", headers=admin_headers)
    assert listed.status_code == 200
    assert listed.json()[0]["message_count"] == 0

    deleted = await client.delete(
        f"/api/v1/conversations/{conversation_id}", headers=admin_headers
    )
    assert deleted.status_code == 204


async def test_rename_conversation(client: AsyncClient, admin_headers, member_headers):
    conversation_id = await _setup_product_and_conversation(client, admin_headers)
    renamed = await client.patch(
        f"/api/v1/conversations/{conversation_id}",
        json={"title": "Espresso troubleshooting"},
        headers=admin_headers,
    )
    assert renamed.status_code == 200, renamed.text
    body = renamed.json()
    assert body["title"] == "Espresso troubleshooting"
    assert body["message_count"] == 0

    detail = await client.get(
        f"/api/v1/conversations/{conversation_id}", headers=admin_headers
    )
    assert detail.json()["title"] == "Espresso troubleshooting"

    # Members cannot rename someone else's conversation.
    forbidden = await client.patch(
        f"/api/v1/conversations/{conversation_id}",
        json={"title": "hijack"},
        headers=member_headers,
    )
    assert forbidden.status_code == 404


async def test_rename_rejects_blank_title(client: AsyncClient, admin_headers):
    conversation_id = await _setup_product_and_conversation(client, admin_headers)
    response = await client.patch(
        f"/api/v1/conversations/{conversation_id}",
        json={"title": "   "},
        headers=admin_headers,
    )
    assert response.status_code == 422
