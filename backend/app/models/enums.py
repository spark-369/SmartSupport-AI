"""Enum types and values shared across ORM models."""

from __future__ import annotations

from enum import Enum


def enum_values(enum_cls: type[Enum]) -> list[str]:
    """``values_callable`` helper so SQLAlchemy persists enum *values* (not names)."""
    return [member.value for member in enum_cls]


class UserRole(str, Enum):
    ADMIN = "admin"
    USER = "user"


class DocumentStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    READY = "ready"
    FAILED = "failed"


class MessageRole(str, Enum):
    USER = "user"
    ASSISTANT = "assistant"


class TicketStatus(str, Enum):
    OPEN = "open"
    ESCALATED = "escalated"
    RESOLVED = "resolved"
    DISMISSED = "dismissed"


DEFAULT_CONVERSATION_TITLE = "New conversation"
