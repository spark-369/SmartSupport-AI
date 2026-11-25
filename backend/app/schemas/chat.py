"""Chat schemas (conversations, messages, streaming request bodies)."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.enums import MessageRole
from app.schemas.ai import SourceRef


class ConversationCreate(BaseModel):
    product_id: uuid.UUID


class ConversationUpdate(BaseModel):
    title: str = Field(min_length=1, max_length=200)

    @field_validator("title")
    @classmethod
    def _title_not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Title cannot be blank.")
        return value


class MessageCreate(BaseModel):
    content: str = Field(min_length=1, max_length=4000)


class MessagePublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    role: MessageRole
    content: str
    sources: list[SourceRef] = Field(default_factory=list)
    follow_ups: list[str] = Field(default_factory=list)
    confidence: float | None = None
    found_in_manual: bool | None = None
    latency_ms: int | None = None
    created_at: datetime


class ConversationPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: uuid.UUID
    product_id: uuid.UUID | None
    product_name: str | None
    title: str
    message_count: int = 0
    created_at: datetime
    updated_at: datetime


class ConversationDetail(ConversationPublic):
    messages: list[MessagePublic] = Field(default_factory=list)
