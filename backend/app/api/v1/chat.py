"""Chat endpoints: conversations CRUD + SSE message streaming."""

from __future__ import annotations

import json
import uuid
from collections.abc import AsyncIterator

from fastapi import APIRouter, Depends, Response, status
from fastapi.responses import StreamingResponse

from app.api.deps import CurrentUser, DbSession, RAGDep, EmbedderDep, user_rate_limit
from app.core.config import get_settings
from app.core.errors import ConflictError
from app.db.session import SessionFactory
from app.models.enums import DEFAULT_CONVERSATION_TITLE
from app.schemas.chat import (
    ConversationCreate,
    ConversationDetail,
    ConversationPublic,
    ConversationUpdate,
    MessageCreate,
    MessagePublic,
)
from app.schemas.ticket import TicketFromConversation, TicketPublic
from app.services import chat_service, product_service, triage_service
from app.services.rag.pipeline import PipelineContext, SupportPipeline

router = APIRouter(prefix="/conversations", tags=["chat"])

_chat_limit = user_rate_limit("chat", get_settings().rate_limit_chat_per_minute, 60)
_triage_limit = user_rate_limit("triage", get_settings().rate_limit_triage_per_minute, 60)

SSE_HEADERS = {
    "Cache-Control": "no-cache",
    "Connection": "keep-alive",
    "X-Accel-Buffering": "no",
}


def sse_encode(event: str, data: dict) -> str:
    """Encode one Server-Sent Event frame."""
    return f"event: {event}\ndata: {json.dumps(data, default=str)}\n\n"


@router.post("", response_model=ConversationPublic, status_code=status.HTTP_201_CREATED)
async def create_conversation(
    payload: ConversationCreate, user: CurrentUser, db: DbSession
) -> ConversationPublic:
    conversation = await chat_service.create_conversation(db, user.id, payload.product_id)
    return ConversationPublic.model_validate(conversation)


@router.get("", response_model=list[ConversationPublic])
async def list_conversations(user: CurrentUser, db: DbSession) -> list[ConversationPublic]:
    rows = await chat_service.list_conversations(db, user.id)
    return [
        ConversationPublic.model_validate(conv).model_copy(update={"message_count": count})
        for conv, count in rows
    ]


@router.get("/{conversation_id}", response_model=ConversationDetail)
async def get_conversation(conversation_id: uuid.UUID, user: CurrentUser, db: DbSession) -> ConversationDetail:
    conversation = await chat_service.get_conversation(db, user.id, conversation_id)
    messages = await chat_service.get_messages(db, conversation.id)
    # Build explicitly — model_validate on the ORM object would lazy-load `messages`.
    base = ConversationPublic.model_validate(conversation).model_dump()
    base.pop("message_count", None)
    detail = ConversationDetail(
        **base,
        message_count=len(messages),
        messages=[MessagePublic.model_validate(m) for m in messages],
    )
    return detail


@router.patch("/{conversation_id}", response_model=ConversationPublic)
async def rename_conversation(
    conversation_id: uuid.UUID,
    payload: ConversationUpdate,
    user: CurrentUser,
    db: DbSession,
) -> ConversationPublic:
    """Rename a conversation (the owner only)."""
    conversation = await chat_service.get_conversation(db, user.id, conversation_id)
    updated = await chat_service.rename_conversation(db, conversation, payload.title)
    public = ConversationPublic.model_validate(updated)
    return public.model_copy(
        update={"message_count": await chat_service.count_messages(db, updated.id)}
    )


@router.delete("/{conversation_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_conversation(conversation_id: uuid.UUID, user: CurrentUser, db: DbSession) -> Response:
    conversation = await chat_service.get_conversation(db, user.id, conversation_id)
    await chat_service.delete_conversation(db, conversation)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/{conversation_id}/tickets", response_model=TicketPublic, status_code=status.HTTP_201_CREATED)
async def create_ticket_from_conversation(
    conversation_id: uuid.UUID,
    body: TicketFromConversation,
    user: CurrentUser,
    db: DbSession,
    rag: RAGDep,
    embedder: EmbedderDep,
    _rate: None = Depends(_triage_limit),
) -> TicketPublic:
    """Escalate this support chat: AI-triage a customer message into a ticket.

    Triages the latest user message (or the question preceding the given
    message — e.g. escalating a not-grounded answer) with the conversation's
    product as context and its manual excerpts for grounding.
    """
    ticket = await triage_service.create_ticket_from_conversation(
        db, rag, embedder, user, conversation_id, body.message_id
    )
    return TicketPublic.model_validate(ticket)


@router.post("/{conversation_id}/messages/stream")
async def stream_message(
    conversation_id: uuid.UUID,
    body: MessageCreate,
    user: CurrentUser,
    db: DbSession,
    rag: RAGDep,
    embedder: EmbedderDep,
    _rate: None = Depends(_chat_limit),
) -> StreamingResponse:
    """Ask a question; returns ``text/event-stream`` with live progress + grounded answer.

    Events: ``status`` → ``sources`` → ``status`` → ``token``* → ``answer`` → ``done``
    (or ``error``). ``token`` frames stream the answer prose while it is generated;
    the user turn is persisted atomically with the assistant reply (clean retries).
    """
    conversation = await chat_service.get_conversation(db, user.id, conversation_id)
    if conversation.product_id is None:
        raise ConflictError("The product for this conversation no longer exists.")
    await product_service.get_product_or_404(db, conversation.product_id)

    generate_title = conversation.title == DEFAULT_CONVERSATION_TITLE

    pipeline = SupportPipeline(
        rag,
        embedder,
        SessionFactory,
        top_k=get_settings().retrieval_top_k,
        min_score=get_settings().retrieval_min_score,
        history_len=get_settings().rag_history_messages,
    )
    ctx = PipelineContext(
        conversation_id=conversation.id,
        product_id=conversation.product_id,
        product_name=conversation.product_name or "the product",
        question=body.content,
        generate_title=generate_title,
    )

    async def event_stream() -> AsyncIterator[str]:
        try:
            async for event in pipeline.run(ctx):
                yield sse_encode(event.type, event.payload)
        except Exception:  # pragma: no cover — pipeline already guards internally
            yield sse_encode("error", {"code": "stream_error", "message": "The response stream failed."})

    return StreamingResponse(event_stream(), media_type="text/event-stream", headers=SSE_HEADERS)
