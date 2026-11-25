"""Analytics overview endpoint tests (admin insights)."""

from __future__ import annotations

import uuid

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Conversation, Message, MessageRole, Product, User


async def _seed_activity(db: AsyncSession) -> None:
    user = User(email=f"seed-{uuid.uuid4().hex[:6]}@test.io", hashed_password="x", full_name="Seed User")
    product = Product(name="Seed Product", slug=f"seed-{uuid.uuid4().hex[:8]}")
    db.add_all([user, product])
    await db.flush()

    conversation = Conversation(user_id=user.id, product_id=product.id, product_name=product.name)
    db.add(conversation)
    await db.flush()

    # Exchange 1: grounded answer.
    db.add_all(
        [
            Message(
                conversation_id=conversation.id,
                role=MessageRole.USER,
                content="How often to descale the machine?",
            ),
            Message(
                conversation_id=conversation.id,
                role=MessageRole.ASSISTANT,
                content="Descale quarterly with one sachet.",
                confidence=0.9,
                found_in_manual=True,
                latency_ms=1200,
            ),
        ]
    )
    await db.commit()

    # Exchange 2: not grounded → knowledge gap.
    db.add_all(
        [
            Message(
                conversation_id=conversation.id,
                role=MessageRole.USER,
                content="What is the warranty period exactly?",
            ),
            Message(
                conversation_id=conversation.id,
                role=MessageRole.ASSISTANT,
                content="I could not find this in the manual.",
                confidence=0.3,
                found_in_manual=False,
                latency_ms=900,
            ),
        ]
    )
    await db.commit()


async def test_overview_aggregates(db: AsyncSession, client: AsyncClient, admin_headers):
    await _seed_activity(db)
    response = await client.get("/api/v1/analytics/overview", headers=admin_headers)
    assert response.status_code == 200, response.text
    data = response.json()

    totals = data["totals"]
    assert totals["conversations"] == 1
    assert totals["user_questions"] == 2
    assert totals["assistant_answers"] == 2
    assert totals["active_users"] == 1
    assert totals["grounded_rate"] == 0.5
    assert abs(totals["avg_confidence"] - 0.6) < 1e-6
    assert totals["avg_latency_ms"] == 1050

    per_product = data["per_product"]
    assert len(per_product) == 1
    assert per_product[0]["product_name"] == "Seed Product"
    assert per_product[0]["questions"] == 2
    assert per_product[0]["unanswered"] == 1
    assert per_product[0]["avg_confidence"] == 0.6

    gaps = data["knowledge_gaps"]
    assert len(gaps) == 1
    assert gaps[0]["question"] == "What is the warranty period exactly?"
    assert gaps[0]["product_name"] == "Seed Product"
    assert "manual" in gaps[0]["answer_preview"].lower()

    top_questions = {item["question"]: item["count"] for item in data["top_questions"]}
    assert top_questions["how often to descale the machine?"] == 1
    assert top_questions["what is the warranty period exactly?"] == 1


async def test_overview_requires_admin(client: AsyncClient, admin_headers, member_headers):
    member = await client.get("/api/v1/analytics/overview", headers=member_headers)
    assert member.status_code == 403

    anonymous = await client.get("/api/v1/analytics/overview")
    assert anonymous.status_code == 401


async def test_overview_empty_workspace(client: AsyncClient, admin_headers):
    response = await client.get("/api/v1/analytics/overview", headers=admin_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["totals"]["conversations"] == 0
    assert data["totals"]["grounded_rate"] is None
    assert data["knowledge_gaps"] == []
    assert data["top_questions"] == []