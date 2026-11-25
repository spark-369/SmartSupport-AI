"""Message model — one turn (user or assistant) inside a conversation."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, Any

from sqlalchemy import Boolean, Enum as SAEnum, Float, ForeignKey, Integer, Text, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin
from app.models.enums import MessageRole, enum_values

if TYPE_CHECKING:
    from app.models.conversation import Conversation


class Message(Base, TimestampMixin):
    __tablename__ = "messages"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    conversation_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("conversations.id", ondelete="CASCADE"), index=True, nullable=False
    )
    role: Mapped[MessageRole] = mapped_column(
        SAEnum(MessageRole, native_enum=False, values_callable=enum_values, length=16, validate_strings=True),
        nullable=False,
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)
    # For assistant messages: list of SourceRef dicts (chunk_id, document_name, quote, score, page).
    sources: Mapped[list[dict[str, Any]]] = mapped_column(
        JSONB, default=list, server_default=text("'[]'::jsonb"), nullable=False
    )
    # For assistant messages: suggested follow-up questions shown as chips.
    follow_ups: Mapped[list[str]] = mapped_column(
        JSONB, default=list, server_default=text("'[]'::jsonb"), nullable=False
    )
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    found_in_manual: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)

    conversation: Mapped["Conversation"] = relationship(back_populates="messages")
