"""Analytics schemas (admin insights over conversations & answers)."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel


class AnalyticsTotals(BaseModel):
    conversations: int = 0
    user_questions: int = 0
    assistant_answers: int = 0
    active_users: int = 0
    avg_confidence: float | None = None
    grounded_rate: float | None = None
    avg_latency_ms: int | None = None


class ProductAnalytics(BaseModel):
    product_id: uuid.UUID
    product_name: str
    conversations: int = 0
    questions: int = 0
    avg_confidence: float | None = None
    unanswered: int = 0


class KnowledgeGap(BaseModel):
    """A question the bot could not ground in the manuals — content to add."""

    conversation_id: uuid.UUID
    product_name: str | None
    question: str
    answer_preview: str
    confidence: float | None
    created_at: datetime


class TopQuestion(BaseModel):
    question: str
    count: int


class AnalyticsOverview(BaseModel):
    totals: AnalyticsTotals
    per_product: list[ProductAnalytics]
    knowledge_gaps: list[KnowledgeGap]
    top_questions: list[TopQuestion]