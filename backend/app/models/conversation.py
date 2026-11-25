"""Conversation model — a support chat session scoped to a user + product."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin
from app.models.enums import DEFAULT_CONVERSATION_TITLE

if TYPE_CHECKING:
    from app.models.message import Message
    from app.models.product import Product
    from app.models.user import User


class Conversation(Base, TimestampMixin):
    __tablename__ = "conversations"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    product_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("products.id", ondelete="SET NULL"), nullable=True
    )
    # Snapshot so history remains readable if the product is later removed.
    product_name: Mapped[str | None] = mapped_column(String(160), nullable=True)
    title: Mapped[str] = mapped_column(String(200), default=DEFAULT_CONVERSATION_TITLE, nullable=False)

    user: Mapped["User"] = relationship(back_populates="conversations")
    product: Mapped["Product | None"] = relationship()
    messages: Mapped[list["Message"]] = relationship(
        back_populates="conversation", cascade="all, delete-orphan", passive_deletes=True
    )
