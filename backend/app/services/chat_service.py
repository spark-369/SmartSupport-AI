"""Conversation/message persistence helpers."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import NotFoundError
from app.models.conversation import Conversation
from app.models.enums import DEFAULT_CONVERSATION_TITLE, MessageRole
from app.models.message import Message
from app.models.product import Product


async def create_conversation(session: AsyncSession, user_id: uuid.UUID, product_id: uuid.UUID) -> Conversation:
    product = await session.get(Product, product_id)
    if product is None:
        raise NotFoundError("Product not found.")
    conversation = Conversation(user_id=user_id, product_id=product.id, product_name=product.name)
    session.add(conversation)
    await session.commit()
    await session.refresh(conversation)
    return conversation


async def list_conversations(session: AsyncSession, user_id: uuid.UUID) -> list[tuple[Conversation, int]]:
    """Conversations (newest activity first) with message counts."""
    stmt = (
        select(Conversation, func.count(Message.id))
        .outerjoin(Message, Message.conversation_id == Conversation.id)
        .where(Conversation.user_id == user_id)
        .group_by(Conversation.id)
        .order_by(Conversation.updated_at.desc())
    )
    return [(conv, count) for conv, count in (await session.execute(stmt)).all()]


async def get_conversation(session: AsyncSession, user_id: uuid.UUID, conversation_id: uuid.UUID) -> Conversation:
    conversation = await session.get(Conversation, conversation_id)
    if conversation is None or conversation.user_id != user_id:
        raise NotFoundError("Conversation not found.")
    return conversation


async def get_messages(session: AsyncSession, conversation_id: uuid.UUID) -> list[Message]:
    result = await session.execute(
        select(Message).where(Message.conversation_id == conversation_id).order_by(Message.created_at)
    )
    return list(result.scalars().all())


async def get_recent_history(
    session: AsyncSession, conversation_id: uuid.UUID, limit: int
) -> list[Message]:
    """Last ``limit`` messages in chronological order."""
    result = await session.execute(
        select(Message)
        .where(Message.conversation_id == conversation_id)
        .order_by(Message.created_at.desc(), Message.id.desc())
        .limit(limit)
    )
    return list(reversed(result.scalars().all()))


async def append_message(
    session: AsyncSession,
    conversation_id: uuid.UUID,
    role: MessageRole,
    content: str,
    *,
    sources: list[dict] | None = None,
    follow_ups: list[str] | None = None,
    confidence: float | None = None,
    found_in_manual: bool | None = None,
    latency_ms: int | None = None,
) -> Message:
    message = Message(
        conversation_id=conversation_id,
        role=role,
        content=content,
        sources=sources or [],
        follow_ups=follow_ups or [],
        confidence=confidence,
        found_in_manual=found_in_manual,
        latency_ms=latency_ms,
    )
    session.add(message)
    conversation = await session.get(Conversation, conversation_id)
    if conversation is not None:
        conversation.updated_at = datetime.now(UTC)
    await session.flush()
    return message


async def set_title(session: AsyncSession, conversation: Conversation, title: str) -> None:
    conversation.title = title.strip()[:200] or DEFAULT_CONVERSATION_TITLE
    await session.commit()


async def count_messages(session: AsyncSession, conversation_id: uuid.UUID) -> int:
    return int(
        await session.scalar(
            select(func.count()).select_from(Message).where(Message.conversation_id == conversation_id)
        )
        or 0
    )


async def rename_conversation(session: AsyncSession, conversation: Conversation, title: str) -> Conversation:
    conversation.title = title.strip()[:200] or DEFAULT_CONVERSATION_TITLE
    await session.commit()
    await session.refresh(conversation)
    return conversation


async def delete_conversation(session: AsyncSession, conversation: Conversation) -> None:
    await session.delete(conversation)
    await session.commit()


async def count_conversations(session: AsyncSession, user_id: uuid.UUID) -> int:
    return int(await session.scalar(select(func.count()).select_from(Conversation).where(Conversation.user_id == user_id)) or 0)


async def delete_all_for_user(session: AsyncSession, user_id: uuid.UUID) -> None:
    await session.execute(delete(Conversation).where(Conversation.user_id == user_id))
