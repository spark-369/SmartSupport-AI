"""Support ticket — a triaged customer message with escalation workflow."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import DateTime, Enum as SAEnum, ForeignKey, Integer, String, Text, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin
from app.models.enums import TicketStatus, enum_values

if TYPE_CHECKING:
    from app.models.product import Product
    from app.models.user import User


class Ticket(Base, TimestampMixin):
    __tablename__ = "tickets"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), index=True, nullable=True
    )
    product_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("products.id", ondelete="SET NULL"), nullable=True
    )
    # Chat origin: the conversation (and message) this ticket was escalated from.
    conversation_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("conversations.id", ondelete="SET NULL"), index=True, nullable=True
    )
    source_message_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("messages.id", ondelete="SET NULL"), nullable=True
    )
    raw_message: Mapped[str] = mapped_column(Text, nullable=False)
    # Snapshot so history remains readable if the product is later removed.
    product_name: Mapped[str | None] = mapped_column(String(160), nullable=True)
    status: Mapped[TicketStatus] = mapped_column(
        SAEnum(TicketStatus, native_enum=False, values_callable=enum_values, length=16, validate_strings=True),
        default=TicketStatus.OPEN,
        index=True,
        nullable=False,
    )

    # --- AI triage snapshot (immutable after creation) ---
    category: Mapped[str] = mapped_column(String(40), nullable=False)
    urgency: Mapped[str] = mapped_column(String(16), index=True, nullable=False)
    sentiment: Mapped[str] = mapped_column(String(16), nullable=False)
    needs_human: Mapped[bool] = mapped_column(default=False, index=True, nullable=False)
    escalation_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    extracted_data: Mapped[dict[str, Any]] = mapped_column(
        JSONB, default=dict, server_default=text("'{}'::jsonb"), nullable=False
    )
    triage_latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # --- Human workflow ---
    resolution_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    resolved_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    creator: Mapped["User | None"] = relationship(foreign_keys=[created_by])
    product: Mapped["Product | None"] = relationship()