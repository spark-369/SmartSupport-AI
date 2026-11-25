"""SupportPipeline orchestration tests with fake AI components."""

from __future__ import annotations

import json
import uuid
from collections.abc import AsyncIterator

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.db.session import SessionFactory
from app.models import Conversation, Document, DocumentStatus, Message, MessageRole, Product
from app.schemas.ai import Answer, ConversationTitle, QueryRewrite
from app.services.rag.pipeline import PipelineContext, SupportPipeline
from app.services.retrieval import RetrievedChunk

FAKE_VECTOR = [0.5] * 8


class FakeRAG:
    async def rewrite_query(self, question: str, history: list[tuple[str, str]]) -> QueryRewrite:
        return QueryRewrite(rewritten_query=f"rewrite::{question}", keywords=["kw"])

    async def generate_answer(self, question, results, product_name) -> Answer:
        return self._fake_answer(question, results)

    async def stream_answer_json(self, question, results, product_name) -> AsyncIterator[str]:
        """Yield the fake answer JSON in small chunks (like Ollama would)."""
        payload = json.dumps(self._fake_answer(question,results).model_dump())
        chunk_size = 7
        for start in range(0, len(payload), chunk_size):
            yield payload[start : start + chunk_size]

    @staticmethod
    def _fake_answer(question, results) -> Answer:
        return Answer(
            answer=f"Grounded answer for: {question}",
            confidence=0.8,
            found_in_manual=bool(results),
            cited_excerpts=[1] if results else [],
            follow_up_questions=["Next?", "Why?"],
        )

    async def generate_title(self, question: str, answer_text: str) -> ConversationTitle:
        return ConversationTitle(title="Fake title")


class FakeEmbedder:
    async def embed_query(self, text: str) -> list[float]:
        return FAKE_VECTOR


def _fake_retrieve(session, product_id, vector, *, top_k=None, min_score=None):
    async def _inner() -> list[RetrievedChunk]:
        return [
            RetrievedChunk(
                chunk_id="chunk-1",
                document_name="manual.md",
                content="Descale quarterly.",
                score=0.77,
                page=6,
                chunk_index=3,
            )
        ]

    return _inner()


@pytest.fixture()
def pipeline() -> SupportPipeline:
    return SupportPipeline(
        FakeRAG(),
        FakeEmbedder(),
        SessionFactory,
        top_k=3,
        min_score=0.1,
        history_len=4,
    )


@pytest.fixture()
async def conversation(db: AsyncSession) -> AsyncIterator[Conversation]:
    product = Product(name="Probe P1", slug=f"probe-{uuid.uuid4().hex[:8]}")
    db.add(product)
    await db.flush()
    conversation = Conversation(
        user_id=None,  # replaced below
        product_id=product.id,
        product_name=product.name,
    )
    from app.models import User

    user = User(email=f"pipe-{uuid.uuid4().hex[:6]}@test.io", hashed_password="x", full_name="P")
    db.add(user)
    await db.flush()
    conversation.user_id = user.id
    db.add(conversation)
    await db.commit()
    await db.refresh(conversation)
    return conversation


async def test_pipeline_event_sequence_and_persistence(
    pipeline: SupportPipeline, conversation: Conversation, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setattr("app.services.rag.pipeline.retrieve", _fake_retrieve)

    ctx = PipelineContext(
        conversation_id=conversation.id,
        product_id=conversation.product_id,
        product_name=conversation.product_name or "P",
        question="How often to descale?",
        generate_title=True,
    )
    events = [event async for event in pipeline.run(ctx)]
    types = [event.type for event in events]

    assert types[:4] == ["status", "status", "sources", "status"]
    assert types[-2:] == ["answer", "done"]
    assert "token" in types  # streamed deltas were emitted
    assert events[2].payload["sources"][0]["chunk_id"] == "chunk-1"
    answer_message = events[-2].payload["message"]
    assert answer_message["role"] == "assistant"
    assert answer_message["found_in_manual"] is True
    assert answer_message["follow_ups"] == ["Next?", "Why?"]
    assert events[-1].payload["title"] == "Fake title"

    # Streamed tokens concatenate to the full answer prose.
    streamed = "".join(e.payload["delta"] for e in events if e.type == "token")
    assert streamed == "Grounded answer for: How often to descale?"

    async with SessionFactory() as session:
        rows = (
            await session.execute(
                select(Message)
                .where(Message.conversation_id == conversation.id)
                .order_by(Message.created_at)
            )
        ).scalars().all()
        assert len(rows) == 2  # user turn + assistant reply (single commit)
        assert rows[0].role is MessageRole.USER
        assert rows[0].content == "How often to descale?"
        assistant = rows[1]
        assert assistant.role is MessageRole.ASSISTANT
        assert assistant.sources[0]["chunk_id"] == "chunk-1"
        assert assistant.follow_ups == ["Next?", "Why?"]
        refreshed_conv = await session.get(Conversation, conversation.id)
        assert refreshed_conv is not None
        assert refreshed_conv.title == "Fake title"


async def test_pipeline_falls_back_without_streaming(
    pipeline: SupportPipeline, conversation: Conversation, monkeypatch: pytest.MonkeyPatch
):
    """A brain without stream_answer_json still produces the full event flow."""

    class NonStreamingRAG(FakeRAG):
        stream_answer_json = None  # type: ignore[assignment]  # getattr check treats as absent

    # getattr on an instance with a class attribute set to None returns None.
    non_streaming = SupportPipeline(
        NonStreamingRAG(), FakeEmbedder(), SessionFactory, top_k=3, min_score=0.1
    )
    monkeypatch.setattr("app.services.rag.pipeline.retrieve", _fake_retrieve)
    ctx = PipelineContext(
        conversation_id=conversation.id,
        product_id=conversation.product_id,
        product_name="P",
        question="q",
        generate_title=False,
    )
    events = [event async for event in non_streaming.run(ctx)]
    types = [event.type for event in events]
    assert "token" not in types
    assert types[-2:] == ["answer", "done"]


async def test_auto_title_does_not_overwrite_user_rename(
    pipeline: SupportPipeline, conversation: Conversation, monkeypatch: pytest.MonkeyPatch
):
    """Renaming mid-flight must survive the pipeline's auto-title."""
    monkeypatch.setattr("app.services.rag.pipeline.retrieve", _fake_retrieve)
    async with SessionFactory() as session:
        row = await session.get(Conversation, conversation.id)
        row.title = "User renamed this"
        await session.commit()

    ctx = PipelineContext(
        conversation_id=conversation.id,
        product_id=conversation.product_id,
        product_name="P",
        question="q",
        generate_title=True,  # flagged at request time, before the rename
    )
    events = [event async for event in pipeline.run(ctx)]
    assert events[-1].payload["title"] is None  # auto-title skipped

    async with SessionFactory() as session:
        row = await session.get(Conversation, conversation.id)
        assert row.title == "User renamed this"


async def test_pipeline_handles_model_failure(
    pipeline: SupportPipeline, conversation: Conversation
):
    class BrokenRAG(FakeRAG):
        async def stream_answer_json(self, *args, **kwargs):
            raise RuntimeError("ollama exploded")

        async def generate_answer(self, *args, **kwargs):
            raise RuntimeError("ollama exploded")

    broken = SupportPipeline(
        BrokenRAG(), FakeEmbedder(), SessionFactory, top_k=3, min_score=0.1
    )
    ctx = PipelineContext(
        conversation_id=conversation.id,
        product_id=conversation.product_id,
        product_name="P",
        question="q",
        generate_title=False,
    )
    events = [event async for event in broken.run(ctx)]
    assert events[-1].type == "error"
    assert events[-1].payload["code"] == "pipeline_error"

    # Nothing was persisted — a retry starts clean.
    async with SessionFactory() as session:
        rows = (
            await session.execute(select(Message).where(Message.conversation_id == conversation.id))
        ).scalars().all()
        assert rows == []
