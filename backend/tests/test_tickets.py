"""Ticket triage endpoint tests — tickets are created from support chats."""

from __future__ import annotations

import uuid

import httpx
from httpx import AsyncClient

from app.api.deps import get_embedder, get_rag
from app.models import Message, MessageRole
from app.schemas.ai import Answer, TicketExtracted, TicketTriage
from app.services.retrieval import RetrievedChunk
from tests.test_pipeline import FakeEmbedder

COMPLAINT = (
    "I received my Blue Shirt yesterday and the sleeve is already torn. "
    "This is unacceptable — I want a replacement shipped immediately or I will dispute the charge."
)

TRIAGE_CALLS: list[dict] = []


def _fake_rag(answer_found: bool = True, **overrides) -> object:
    defaults: dict = {
        "category": "complaint_exchange",
        "urgency": "high",
        "sentiment": "frustrated",
        "extracted_data": TicketExtracted(
            product="Blue Shirt",
            issue="Torn sleeve on arrival",
            requested_action="Replacement",
            topics=["torn", "sleeve", "replacement"],
        ),
        "needs_human": True,
        "escalation_reason": "Damaged goods with a chargeback threat need a human decision.",
        "summary": "Customer wants a replacement for a shirt that arrived with a torn sleeve.",
    }
    defaults.update(overrides)
    triage = TicketTriage(**defaults)

    class FakeTriageRAG:
        async def analyze_ticket(
            self,
            message: str,
            product_context: str | None = None,
            manual_context: list[RetrievedChunk] | None = None,
        ):
            TRIAGE_CALLS.append(
                {
                    "message": message,
                    "product_context": product_context,
                    "manual_context": manual_context or [],
                }
            )
            return triage

        async def generate_answer(self, question, results, product_name):
            return Answer(
                answer="Grounded manual answer",
                confidence=0.85,
                found_in_manual=answer_found,
                cited_excerpts=[1],
                follow_up_questions=[],
            )

    return FakeTriageRAG()


def _patch_manual_retrieval(monkeypatch, content: str = "Descale every 3 months.") -> None:
    async def fake_retrieve(session, product_id, vector, *, top_k=None, min_score=None):
        return [
            RetrievedChunk(
                chunk_id="chunk-1",
                document_name="manual.md",
                content=content,
                score=0.9,
                page=6,
                chunk_index=0,
            )
        ]

    monkeypatch.setattr("app.services.triage_service.retrieve", fake_retrieve)


async def _setup_conversation_with_message(
    client: AsyncClient, app, headers: dict[str, str], db, question: str = COMPLAINT,
    product_id: str | None = None,
) -> dict:
    """Product (admin-created when the caller is a member) → conversation → user message."""
    if product_id is None:
        product = await client.post("/api/v1/products", json={"name": "Triage Probe"}, headers=headers)
        product_id = product.json()["id"]
    conversation = await client.post(
        "/api/v1/conversations", json={"product_id": product_id}, headers=headers
    )
    conversation_id = uuid.UUID(conversation.json()["id"])
    message = Message(conversation_id=conversation_id, role=MessageRole.USER, content=question)
    db.add(message)
    await db.commit()
    await db.refresh(message)
    return {"conversation_id": conversation_id, "message_id": message.id, "product_id": product_id}


async def _create_ticket(
    client: AsyncClient,
    app,
    headers: dict[str, str],
    conversation_id: uuid.UUID,
    message_id: uuid.UUID | None = None,
    _rag_kwargs: dict | None = None,
) -> httpx.Response:
    app.dependency_overrides[get_rag] = lambda: _fake_rag(**(_rag_kwargs or {}))
    app.dependency_overrides[get_embedder] = lambda: FakeEmbedder()
    body = {"message_id": str(message_id)} if message_id else {}
    return await client.post(
        f"/api/v1/conversations/{conversation_id}/tickets", json=body, headers=headers
    )


async def test_create_ticket_from_chat(
    client: AsyncClient, app, admin_headers, db, monkeypatch
):
    _patch_manual_retrieval(monkeypatch)
    ids = await _setup_conversation_with_message(client, app, admin_headers, db)
    response = await _create_ticket(client, app, admin_headers, ids["conversation_id"])
    assert response.status_code == 201, response.text
    ticket = response.json()

    assert ticket["conversation_id"] == str(ids["conversation_id"])
    assert ticket["source_message_id"] == str(ids["message_id"])
    assert ticket["raw_message"] == COMPLAINT  # the chat question became the ticket
    assert ticket["product_name"] == "Triage Probe"  # context came from the conversation
    assert ticket["category"] == "complaint_exchange"

    # Deterministic escalation: the manuals answer it → no human needed,
    # urgency downgraded, suggested reply replaced by the grounded answer.
    assert ticket["needs_human"] is False
    assert ticket["urgency"] == "medium"
    assert ticket["triage_latency_ms"] >= 0
    assert ticket["status"] == "open"


async def test_requested_action_fallback_and_topic_cleanup(
    client: AsyncClient, app, admin_headers, db, monkeypatch
):
    """A null requested_action is inferred from an explicit request verb, and
    category-slug noise the 0.5B model leaks into topics is stripped."""
    _patch_manual_retrieval(monkeypatch)
    ids = await _setup_conversation_with_message(
        client, app, admin_headers, db, question="give me sugar"
    )
    response = await _create_ticket(
        client,
        app,
        admin_headers,
        ids["conversation_id"],
        _rag_kwargs={
            "extracted_data": TicketExtracted(
                product="Triage Probe",
                issue="missing sugar",
                requested_action=None,
                topics=["shipping_logistics", "sugar", "Sugar", "order"],
            ),
        },
    )
    assert response.status_code == 201, response.text
    ticket = response.json()
    # The queue wants the solution action, not the customer's words.
    assert ticket["extracted_data"]["requested_action"] == "deliver sugar"
    # slug dropped, case-dedupe applied
    assert ticket["extracted_data"]["topics"] == ["sugar", "order"]


async def test_triage_grounded_in_manual_context(
    client: AsyncClient, app, admin_headers, db, monkeypatch
):
    """The triage chain receives retrieved manual excerpts for its suggested reply."""
    _patch_manual_retrieval(monkeypatch)
    TRIAGE_CALLS.clear()
    ids = await _setup_conversation_with_message(client, app, admin_headers, db)
    response = await _create_ticket(client, app, admin_headers, ids["conversation_id"])
    assert response.status_code == 201, response.text

    assert len(TRIAGE_CALLS) == 1
    call = TRIAGE_CALLS[-1]
    assert call["message"] == COMPLAINT
    assert call["product_context"] == "Triage Probe"
    assert len(call["manual_context"]) == 1
    assert call["manual_context"][0].content == "Descale every 3 months."


async def test_escalation_reason_fallback(
    client: AsyncClient, app, admin_headers, db, monkeypatch
):
    """Not answerable from the manuals → forced escalation with a clear reason."""
    _patch_manual_retrieval(monkeypatch)
    ids = await _setup_conversation_with_message(client, app, admin_headers, db)
    response = await _create_ticket(
        client,
        app,
        admin_headers,
        ids["conversation_id"],
        _rag_kwargs={"answer_found": False, "escalation_reason": None},
    )
    assert response.status_code == 201, response.text
    ticket = response.json()
    assert ticket["needs_human"] is True
    assert ticket["escalation_reason"] == "Not answerable from the available manuals."


async def test_escalate_assistant_answer_maps_to_question(
    client: AsyncClient, app, admin_headers, db
):
    ids = await _setup_conversation_with_message(client, app, admin_headers, db)
    # An assistant answer right after the user question (same commit → same timestamp).
    answer = Message(
        conversation_id=ids["conversation_id"],
        role=MessageRole.ASSISTANT,
        content="I could not find this in the manual.",
        found_in_manual=False,
    )
    db.add(answer)
    await db.commit()
    await db.refresh(answer)

    # Escalating the ANSWER must triage the preceding user question.
    response = await _create_ticket(
        client, app, admin_headers, ids["conversation_id"], answer.id
    )
    assert response.status_code == 201, response.text
    ticket = response.json()
    assert ticket["raw_message"] == COMPLAINT
    assert ticket["source_message_id"] == str(ids["message_id"])


async def test_explicit_user_message_id(client: AsyncClient, app, admin_headers, db):
    ids = await _setup_conversation_with_message(client, app, admin_headers, db, question="First question about setup?")
    second = Message(conversation_id=ids["conversation_id"], role=MessageRole.USER, content="Second question about the warranty?")
    db.add(second)
    await db.commit()
    await db.refresh(second)

    # Default → latest user message.
    default = await _create_ticket(client, app, admin_headers, ids["conversation_id"])
    assert default.json()["raw_message"] == "Second question about the warranty?"

    # Explicit user message id → that message.
    explicit = await _create_ticket(
        client, app, admin_headers, ids["conversation_id"], ids["message_id"]
    )
    assert explicit.json()["raw_message"] == "First question about setup?"


async def test_conversation_without_user_message_conflict(
    client: AsyncClient, app, admin_headers
):
    product = await client.post("/api/v1/products", json={"name": "Empty Chat"}, headers=admin_headers)
    conversation = await client.post(
        "/api/v1/conversations", json={"product_id": product.json()["id"]}, headers=admin_headers
    )
    app.dependency_overrides[get_rag] = lambda: _fake_rag()
    response = await client.post(
        f"/api/v1/conversations/{conversation.json()['id']}/tickets",
        json={},
        headers=admin_headers,
    )
    assert response.status_code == 409
    assert "no customer message" in response.json()["error"]["message"]


async def test_member_cannot_triage_foreign_conversation(
    client: AsyncClient, app, admin_headers, member_headers, db
):
    ids = await _setup_conversation_with_message(client, app, admin_headers, db)
    app.dependency_overrides[get_rag] = lambda: _fake_rag()
    response = await client.post(
        f"/api/v1/conversations/{ids['conversation_id']}/tickets",
        json={},
        headers=member_headers,
    )
    assert response.status_code == 404  # no existence leak


async def test_queue_visibility_and_filters(client: AsyncClient, app, admin_headers, member_headers, db, monkeypatch):
    _patch_manual_retrieval(monkeypatch)
    ids = await _setup_conversation_with_message(client, app, admin_headers, db)
    created = await _create_ticket(client, app, admin_headers, ids["conversation_id"])
    ticket = created.json()

    # Admin sees the whole desk.
    admin_list = (await client.get("/api/v1/tickets", headers=admin_headers)).json()
    assert [t["id"] for t in admin_list] == [ticket["id"]]

    # Members see only their own tickets.
    member_list = (await client.get("/api/v1/tickets", headers=member_headers)).json()
    assert member_list == []

    # Member escalates their own chat → visible to themselves and the admin.
    admin_product = await client.post(
        "/api/v1/products", json={"name": "Member Probe"}, headers=admin_headers
    )
    member_ids = await _setup_conversation_with_message(
        client, app, member_headers, db, product_id=admin_product.json()["id"]
    )
    member_created = await _create_ticket(client, app, member_headers, member_ids["conversation_id"])
    member_ticket = member_created.json()
    member_list = (await client.get("/api/v1/tickets", headers=member_headers)).json()
    assert [t["id"] for t in member_list] == [member_ticket["id"]]
    admin_list = (await client.get("/api/v1/tickets", headers=admin_headers)).json()
    assert {t["id"] for t in admin_list} == {ticket["id"], member_ticket["id"]}

    # Urgency-ordered queue: the medium-urgency (downgraded) ticket floats up.
    assert admin_list[0]["urgency"] in {"critical", "high", "medium"}

    # Filter: needs_human only.
    filtered = (
        await client.get("/api/v1/tickets?needs_human=true", headers=admin_headers)
    ).json()
    assert all(t["needs_human"] for t in filtered)


async def test_status_workflow_and_rbac(client: AsyncClient, app, admin_headers, member_headers, db):
    ids = await _setup_conversation_with_message(client, app, admin_headers, db)
    created = await _create_ticket(client, app, admin_headers, ids["conversation_id"])
    ticket_id = created.json()["id"]

    # Member cannot touch someone else's ticket (404, no existence leak).
    forbidden = await client.patch(
        f"/api/v1/tickets/{ticket_id}",
        json={"status": "resolved", "resolution_note": "hijack"},
        headers=member_headers,
    )
    assert forbidden.status_code == 404

    # Admin escalates, then resolves.
    escalated = await client.patch(
        f"/api/v1/tickets/{ticket_id}", json={"status": "escalated"}, headers=admin_headers
    )
    assert escalated.status_code == 200
    assert escalated.json()["status"] == "escalated"

    resolved = await client.patch(
        f"/api/v1/tickets/{ticket_id}",
        json={"status": "resolved", "resolution_note": "Replacement shipped"},
        headers=admin_headers,
    )
    assert resolved.status_code == 200
    body = resolved.json()
    assert body["status"] == "resolved"
    assert body["resolved_at"] is not None
    assert body["resolution_note"] == "Replacement shipped"

    # Status filter picks it up.
    resolved_list = (
        await client.get("/api/v1/tickets?status=resolved", headers=admin_headers)
    ).json()
    assert [t["id"] for t in resolved_list] == [ticket_id]


async def test_counts_endpoint(client: AsyncClient, app, admin_headers, db):
    ids = await _setup_conversation_with_message(client, app, admin_headers, db)
    await _create_ticket(client, app, admin_headers, ids["conversation_id"])
    counts = (await client.get("/api/v1/tickets/counts", headers=admin_headers)).json()
    assert counts["open"] == 1
    assert counts["active"] == 1


async def test_manual_message_creation_removed_and_auth(client: AsyncClient, admin_headers):
    # The old body-based POST /tickets is gone — messages come from chats only.
    removed = await client.post(
        "/api/v1/tickets", json={"message": COMPLAINT}, headers=admin_headers
    )
    assert removed.status_code == 405

    anonymous = await client.get("/api/v1/tickets")
    assert anonymous.status_code == 401

    missing = await client.get(f"/api/v1/tickets/{uuid.uuid4()}", headers=admin_headers)
    assert missing.status_code == 404

async def test_queue_filters_search_and_creator(client: AsyncClient, app, admin_headers, db):
    ids = await _setup_conversation_with_message(client, app, admin_headers, db)
    created = (await _create_ticket(client, app, admin_headers, ids["conversation_id"])).json()

    # Creator name is attached to list + detail responses.
    listed = (await client.get("/api/v1/tickets", headers=admin_headers)).json()
    assert listed[0]["created_by_name"] == "Ada Admin"
    detail = await client.get(f"/api/v1/tickets/{created['id']}", headers=admin_headers)
    assert detail.json()["created_by_name"] == "Ada Admin"

    # Urgency filter.
    by_urgency = (
        await client.get("/api/v1/tickets?urgency=high", headers=admin_headers)
    ).json()
    assert [t["id"] for t in by_urgency] == [created["id"]]
    empty = (await client.get("/api/v1/tickets?urgency=low", headers=admin_headers)).json()
    assert empty == []

    # Text search over summary / message / category.
    hit = (await client.get("/api/v1/tickets?search=torn", headers=admin_headers)).json()
    assert [t["id"] for t in hit] == [created["id"]]
    hit2 = (await client.get("/api/v1/tickets?search=complaint exchange", headers=admin_headers)).json()
    assert [t["id"] for t in hit2] == [created["id"]]
    miss = (await client.get("/api/v1/tickets?search=nonexistent-topic", headers=admin_headers)).json()
    assert miss == []


async def test_counts_shape_and_scoping(client: AsyncClient, app, admin_headers, db, monkeypatch):
    _patch_manual_retrieval(monkeypatch)
    ids = await _setup_conversation_with_message(client, app, admin_headers, db)
    await _create_ticket(client, app, admin_headers, ids["conversation_id"])

    counts = (await client.get("/api/v1/tickets/counts", headers=admin_headers)).json()
    assert counts["active"] == 1  # default view = open + escalated
    assert counts["open"] == 1
    assert counts["needs_human"] == 0  # the manuals answered it
    assert counts["medium"] == 1  # urgency downgraded from high
    assert counts["high"] == 0
    assert counts["resolved"] == 0
    assert counts["dismissed"] == 0

    # Dismiss it → "all" drops, dismissed counts up.
    ticket_id = (await client.get("/api/v1/tickets", headers=admin_headers)).json()[0]["id"]
    await client.patch(
        f"/api/v1/tickets/{ticket_id}", json={"status": "dismissed"}, headers=admin_headers
    )
    counts = (await client.get("/api/v1/tickets/counts", headers=admin_headers)).json()
    assert counts["active"] == 0
    assert counts["dismissed"] == 1
