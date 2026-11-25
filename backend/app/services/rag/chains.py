"""LangChain chains over ChatOllama with native JSON-Schema structured output.

Every chain is an LCEL ``RunnableSequence`` (message-builder → model) and passes
``format=Schema.model_json_schema()`` to Ollama, which constrains decoding to the
schema. Responses are validated with ``Schema.model_validate_json`` — there is no
manual/regex parsing of model output anywhere in the codebase.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any, Callable

from langchain_core.messages import AIMessage, BaseMessage, SystemMessage, HumanMessage
from langchain_core.runnables import RunnableLambda, RunnableSerializable
from langchain_ollama import ChatOllama
from pydantic import ValidationError

from app.core.config import Settings, get_settings
from app.core.logging import get_logger
from app.schemas.ai import Answer, ConversationTitle, QueryRewrite, SourceRef, TicketTriage
from app.services.retrieval import RetrievedChunk
from app.services.rag.prompts import (
    ANSWER_HUMAN,
    ANSWER_SYSTEM,
    REWRITE_HUMAN,
    REWRITE_SYSTEM,
    TITLE_HUMAN,
    TITLE_SYSTEM,
    TRIAGE_HUMAN,
    TRIAGE_SYSTEM,
)
from app.services.retrieval import RetrievedChunk

logger = get_logger("rag.chains")


class StructuredOutputError(Exception):
    """The model produced output that failed schema validation (should be rare)."""


def _message_text(message: AIMessage) -> str:
    content = message.content
    if isinstance(content, str):
        return content
    # Some backends return a list of content parts.
    return "".join(part if isinstance(part, str) else str(part) for part in content)


def _validate(schema: type[Any], message: AIMessage):
    try:
        return schema.model_validate_json(_message_text(message))
    except ValidationError as exc:
        logger.error("Structured output failed validation: %s | raw=%.200s", exc, _message_text(message))
        raise StructuredOutputError(f"Model output did not match {schema.__name__}") from exc


def _format_history(history: list[tuple[str, str]], max_turns: int = 6) -> str:
    """Render recent turns as plain lines (truncated to keep prompts small)."""
    if not history:
        return "(no previous messages)"
    lines = []
    for role, content in history[-max_turns:]:
        who = "User" if role == "user" else "Assistant"
        lines.append(f"{who}: {content[:300]}")
    return "\n".join(lines)


def _format_context(results: list[RetrievedChunk]) -> str:
    if not results:
        return "(no excerpts retrieved)"
    blocks = []
    for i, chunk in enumerate(results, start=1):
        page = f", page {chunk.page}" if chunk.page else ""
        blocks.append(
            f"[{i}] id={chunk.chunk_id} (source: {chunk.document_name}{page}, score {chunk.score})\n"
            f"{chunk.content}"
        )
    return "\n\n".join(blocks)


class OllamaRAG:
    """Concrete RAG brain: three structured-output chains over local Ollama models."""

    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or get_settings()

        self._rewrite_chain = self._build_chain(
            temperature=0.0,
            num_predict=256,
            schema=QueryRewrite,
            builder=self._build_rewrite_messages,
        )
        self._answer_chain = self._build_chain(
            temperature=self._settings.llm_temperature,
            num_predict=self._settings.answer_max_tokens,
            schema=Answer,
            builder=self._build_answer_messages,
        )
        self._title_chain = self._build_chain(
            temperature=0.0,
            num_predict=48,
            schema=ConversationTitle,
            builder=self._build_title_messages,
        )
        self._triage_chain = self._build_chain(
            temperature=0.1,
            num_predict=1024,
            schema=TicketTriage,
            builder=self._build_triage_messages,
        )

    # ------------------------------------------------------------------
    # construction helpers
    # ------------------------------------------------------------------

    def _build_chain(
        self,
        temperature: float,
        num_predict: int,
        schema: type[Any],
        builder: Callable[[dict[str, Any]], list[BaseMessage]],
    ) -> RunnableSerializable[dict[str, Any], AIMessage]:
        """message-builder → ChatOllama with native JSON-schema decoding."""
        llm = ChatOllama(
            model=self._settings.llm_model,
            base_url=self._settings.ollama_base_url,
            temperature=temperature,
            num_ctx=self._settings.llm_num_ctx,
            num_predict=num_predict,
            format=schema.model_json_schema(),  # ← Ollama native structured output
        )
        return RunnableLambda(builder) | llm

    # ------------------------------------------------------------------
    # message builders (no f-string templating → manual text is never re-parsed)
    # ------------------------------------------------------------------

    def _build_rewrite_messages(self, inputs: dict[str, Any]) -> list[BaseMessage]:
        return [
            SystemMessage(content=REWRITE_SYSTEM),
            HumanMessage(
                content=REWRITE_HUMAN.format(
                    history=_format_history(inputs.get("history", [])),
                    question=inputs["question"],
                )
            ),
        ]

    def _build_answer_messages(self, inputs: dict[str, Any]) -> list[BaseMessage]:
        return [
            SystemMessage(content=ANSWER_SYSTEM.format(product_name=inputs["product_name"])),
            HumanMessage(
                content=ANSWER_HUMAN.format(
                    context=_format_context(inputs["results"]),
                    question=inputs["question"],
                )
            ),
        ]

    def _build_title_messages(self, inputs: dict[str, Any]) -> list[BaseMessage]:
        return [
            SystemMessage(content=TITLE_SYSTEM),
            HumanMessage(
                content=TITLE_HUMAN.format(
                    question=inputs["question"][:300],
                    answer_summary=inputs["answer_summary"][:300],
                )
            ),
        ]

    def _build_triage_messages(self, inputs: dict[str, Any]) -> list[BaseMessage]:
        manual = inputs.get("manual_context")
        return [
            SystemMessage(content=TRIAGE_SYSTEM),
            HumanMessage(
                content=TRIAGE_HUMAN.format(
                    message=inputs["message"][:4000],
                    product_context=inputs.get("product_context") or "(none provided)",
                    manual_context=_format_context(manual) if manual else "(no manual excerpts retrieved)",
                )
            ),
        ]

    # ------------------------------------------------------------------
    # public API
    # ------------------------------------------------------------------

    async def rewrite_query(self, question: str, history: list[tuple[str, str]]) -> QueryRewrite:
        """Stage 1: turn the raw question into a standalone search query."""
        result = await self._rewrite_chain.ainvoke({"question": question, "history": history})
        return _validate(QueryRewrite, result)

    async def generate_answer(
        self, question: str, results: list[RetrievedChunk], product_name: str
    ) -> Answer:
        """Stage 2: grounded answer citing excerpt numbers (schema-constrained)."""
        result = await self._answer_chain.ainvoke(
            {"question": question, "results": results, "product_name": product_name}
        )
        return _validate(Answer, result)

    async def stream_answer_json(
        self, question: str, results: list[RetrievedChunk], product_name: str
    ) -> AsyncIterator[str]:
        """Stage 2 (streaming): yield raw JSON deltas while the constrained
        answer is being generated.

        The caller accumulates the deltas and validates the complete payload
        with ``Answer.model_validate_json`` — same schema, same guarantee,
        but the UI can start rendering the ``answer`` field while generation
        is still in flight.
        """
        inputs = {"question": question, "results": results, "product_name": product_name}
        async for chunk in self._answer_chain.astream(inputs):
            text = _message_text(chunk)
            if text:
                yield text

    async def generate_title(self, question: str, answer_text: str) -> ConversationTitle:
        """Stage 3: short conversation title for the first exchange."""
        result = await self._title_chain.ainvoke(
            {"question": question, "answer_summary": answer_text}
        )
        return _validate(ConversationTitle, result)

    async def analyze_ticket(
        self,
        message: str,
        product_context: str | None = None,
        manual_context: list[RetrievedChunk] | None = None,
    ) -> TicketTriage:
        """Ticket triage: category / urgency / sentiment / extraction / escalation.

        Runs through the same native ``format`` structured-output technique as
        the RAG chains — constrained decoding, schema-validated, no manual JSON
        parsing. When ``manual_context`` excerpts are supplied the suggested
        reply can ground itself in the manual (simple how-to questions are
        answered instead of escalated).
        """
        result = await self._triage_chain.ainvoke(
            {
                "message": message,
                "product_context": product_context,
                "manual_context": manual_context or [],
            }
        )
        return _validate(TicketTriage, result)
