"""RAG pipeline orchestrator — yields typed events consumed as SSE by the API.

Event contract (``PipelineEvent.type``):
* ``status``  — {stage, detail} progress updates
* ``sources`` — {sources: SourceRef[]} retrieved excerpts (sent before generation)
* ``token``   — {delta: str} incremental answer prose while generation is in flight
* ``answer``  — {message: MessagePublic-dict} persisted assistant message
* ``done``    — {conversation_id, assistant_message_id, title, latency_ms}
* ``error``   — {code, message}
"""

from __future__ import annotations

import time
import uuid
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import Any, Protocol
from uuid import UUID

from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.config import get_settings
from app.core.logging import get_logger
from app.models.conversation import Conversation
from app.models.enums import DEFAULT_CONVERSATION_TITLE, MessageRole
from app.schemas.ai import Answer, SourceRef
from app.schemas.chat import MessagePublic
from app.services import chat_service
from app.services.rag.chains import StructuredOutputError
from app.services.rag.streaming import AnswerFieldStreamer
from app.services.retrieval import RetrievedChunk, retrieve
from app.services.rag.chains import StructuredOutputError

logger = get_logger("rag.pipeline")


@dataclass(frozen=True)
class PipelineEvent:
    type: str
    payload: dict[str, Any] = field(default_factory=dict)


class RAGBrain(Protocol):
    """Anything that can rewrite/answer/title — swap for fakes in tests."""

    async def rewrite_query(self, question: str, history: list[tuple[str, str]]) -> Any: ...

    async def generate_answer(
        self, question: str, results: list[RetrievedChunk], product_name: str
    ) -> Any: ...

    async def generate_title(self, question: str, answer_text: str) -> Any: ...


class Embedder(Protocol):
    async def embed_query(self, text: str) -> list[float]: ...


@dataclass
class PipelineContext:
    conversation_id: UUID
    product_id: UUID | None
    product_name: str
    question: str
    generate_title: bool


class SupportPipeline:
    """Drives the chained stages and yields progress events for SSE streaming."""

    def __init__(
        self,
        rag: RAGBrain,
        embedder: Embedder,
        session_factory: async_sessionmaker[AsyncSession],
        *,
        top_k: int | None = None,
        min_score: float | None = None,
        history_len: int | None = None,
    ) -> None:
        settings = get_settings()
        self._rag = rag
        self._embedder = embedder
        self._session_factory = session_factory
        self._top_k = top_k or settings.retrieval_top_k
        self._min_score = min_score if min_score is not None else settings.retrieval_min_score
        self._history_len = history_len or settings.rag_history_messages

    # ------------------------------------------------------------------

    async def run(self, ctx: PipelineContext) -> AsyncIterator[PipelineEvent]:
        started = time.perf_counter()
        history: list[tuple[str, str]] = []

        async with self._session_factory() as session:
            messages = await chat_service.get_recent_history(session, ctx.conversation_id, self._history_len)
            history = [(m.role.value, m.content) for m in messages]

        try:
            # -- Stage 1: query understanding --------------------------------
            yield PipelineEvent("status", {"stage": "understanding_question", "detail": "Rewriting the question for retrieval"})
            try:
                rewrite = await self._rag.rewrite_query(ctx.question, history)
                search_query = rewrite.rewritten_query or ctx.question
            except Exception as exc:
                logger.warning("Query rewrite failed (%s); using raw question", exc)
                search_query = ctx.question

            # -- Stage 2: retrieval ------------------------------------------
            yield PipelineEvent("status", {"stage": "searching_manual", "detail": f"Searching {ctx.product_name} manuals"})
            vector = await self._embedder.embed_query(search_query)
            async with self._session_factory() as session:
                results = await retrieve(
                    session,
                    ctx.product_id,
                    vector,
                    top_k=self._top_k,
                    min_score=self._min_score,
                )
            yield PipelineEvent("sources", {"sources": [_source_ref(r).model_dump() for r in results]})

            # -- Stage 3: grounded answer (streamed token-by-token) ----------
            yield PipelineEvent("status", {"stage": "generating_answer", "detail": "Composing an answer from the manual"})
            stream = getattr(self._rag, "stream_answer_json", None)
            if stream is not None:
                # Raw JSON deltas are accumulated and the "answer" string field
                # is decoded incrementally so the UI renders prose while the
                # constrained generation is still running. The complete payload
                # is validated through the Answer schema — identical guarantees
                # to the non-streaming path.
                streamer = AnswerFieldStreamer()
                buffer = ""
                async for delta in stream(ctx.question, results, ctx.product_name):
                    buffer += delta
                    text = streamer.feed(buffer)
                    if text:
                        yield PipelineEvent("token", {"delta": text})
                try:
                    answer = Answer.model_validate_json(buffer)
                except ValidationError as exc:
                    logger.error("Structured output failed validation: %s | raw=%.200s", exc, buffer)
                    raise StructuredOutputError("Model output did not match Answer") from exc
            else:
                answer = await self._rag.generate_answer(ctx.question, results, ctx.product_name)

            # -- Persist (single commit: user turn + grounded assistant reply --
            # so a failed/aborted stream leaves nothing behind and retries are clean)
            latency_ms = int((time.perf_counter() - started) * 1000)
            async with self._session_factory() as session:
                await chat_service.append_message(
                    session, ctx.conversation_id, MessageRole.USER, ctx.question
                )
                assistant = await chat_service.append_message(
                    session,
                    ctx.conversation_id,
                    MessageRole.ASSISTANT,
                    answer.answer,
                    sources=_source_refs_payload(results, answer),
                    confidence=float(answer.confidence),
                    found_in_manual=bool(answer.found_in_manual),
                    latency_ms=latency_ms,
                    follow_ups=answer.follow_up_questions,
                )
                await session.refresh(assistant)
                new_title: str | None = None
                if ctx.generate_title:
                    # Re-check under the write lock: the user may have renamed
                    # this conversation while the answer was generating.
                    row = await session.get(Conversation, ctx.conversation_id)
                    if row is not None and row.title == DEFAULT_CONVERSATION_TITLE:
                        try:
                            title = await self._rag.generate_title(ctx.question, answer.answer)
                            new_title = title.title
                            await chat_service.set_title(session, row, new_title)
                        except Exception as exc:
                            logger.warning("Title generation failed: %s", exc)
                    else:
                        logger.info("Skipping auto-title: conversation was renamed by the user")
                await session.commit()

            message_payload = MessagePublic.model_validate(assistant).model_dump(mode="json")
            yield PipelineEvent("answer", {"message": message_payload})
            yield PipelineEvent(
                "done",
                {
                    "conversation_id": str(ctx.conversation_id),
                    "assistant_message_id": str(assistant.id),
                    "title": new_title,
                    "latency_ms": latency_ms,
                    "sources_used": len(_source_refs_payload(results, answer)),
                },
            )
        except StructuredOutputError as exc:
            logger.error("Structured output failure: %s", exc)
            yield PipelineEvent("error", {"code": "model_output_invalid", "message": "The model returned an invalid answer. Please try again."})
        except Exception as exc:
            logger.exception("Pipeline failure")
            yield PipelineEvent("error", {"code": "pipeline_error", "message": f"Something went wrong: {exc.__class__.__name__}"})


def _source_ref(chunk: RetrievedChunk) -> SourceRef:
    return SourceRef(
        chunk_id=chunk.chunk_id,
        document_name=chunk.document_name,
        quote=chunk.content[:240],
        score=float(chunk.score),
        page=chunk.page,
    )


def _source_refs_payload(results: list[RetrievedChunk], answer: Any) -> list[dict[str, Any]]:
    """Resolve the model's cited excerpt **numbers** into SourceRef payloads.

    Quotes/scores/pages come straight from the retrieved chunks — the model never
    echoes them, so the JSON stays small and sources cannot drift from reality.
    Falls back to all retrieved chunks when the model cites nothing usable.
    """
    if not results:
        return []
    picked: list[RetrievedChunk] = []
    seen: set[int] = set()
    for number in getattr(answer, "cited_excerpts", None) or []:
        try:
            index = int(number) - 1
        except (TypeError, ValueError):
            continue
        if 0 <= index < len(results) and index not in seen:
            seen.add(index)
            picked.append(results[index])
    if not picked:
        picked = list(results)
    return [_source_ref(chunk).model_dump() for chunk in picked]
