"""Ticket schemas (AI triage queue)."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import TicketStatus


class TicketFromConversation(BaseModel):
    """Create a ticket from a support-chat message.

    ``message_id`` is optional — when omitted the latest user message of the
    conversation is triaged. An assistant message id is also accepted: its
    preceding user question is used (e.g. escalating a not-grounded answer).
    """

    message_id: uuid.UUID | None = None


class TicketStatusUpdate(BaseModel):
    status: TicketStatus
    resolution_note: str | None = Field(default=None, max_length=2000)


class TicketExtractedData(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    product: str | None = None
    issue: str | None = None
    requested_action: str | None = None
    topics: list[str] = Field(default_factory=list)


class TicketPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    status: TicketStatus
    raw_message: str
    product_id: uuid.UUID | None = None
    product_name: str | None = None
    conversation_id: uuid.UUID | None = None
    source_message_id: uuid.UUID | None = None
    created_by: uuid.UUID | None = None
    created_by_name: str | None = None

    # triage snapshot
    category: str
    urgency: str
    sentiment: str
    needs_human: bool
    escalation_reason: str | None = None
    summary: str
    extracted_data: dict[str, Any] = Field(default_factory=dict)
    triage_latency_ms: int | None = None

    # workflow
    resolution_note: str | None = None
    resolved_at: datetime | None = None

    created_at: datetime
    updated_at: datetime