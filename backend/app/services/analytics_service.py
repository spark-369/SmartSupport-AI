"""Support analytics aggregations (admin insights).

All numbers come from single grouped SQL queries over ``messages`` ×
``conversations`` — no N+1 fetching. The knowledge-gap feed pairs each
not-grounded assistant answer with the user question that produced it via a
correlated scalar subquery (same-transaction messages share ``created_at``,
so ``<=`` correctly resolves the pairing).
"""

from __future__ import annotations

from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from app.models.conversation import Conversation
from app.models.enums import MessageRole
from app.models.message import Message
from app.models.product import Product
from app.schemas.analytics import (
    AnalyticsOverview,
    AnalyticsTotals,
    KnowledgeGap,
    ProductAnalytics,
    TopQuestion,
)

_MIN_QUESTION_LENGTH = 10
_GAP_LIMIT = 8
_TOP_QUESTIONS = 5


async def overview(session: AsyncSession) -> AnalyticsOverview:
    totals_row = (await session.execute(_totals_stmt())).one()
    product_rows = (await session.execute(_per_product_stmt())).all()
    gap_rows = (await session.execute(_knowledge_gaps_stmt())).all()
    question_rows = (await session.execute(_top_questions_stmt())).all()

    return AnalyticsOverview(
        totals=AnalyticsTotals(
            conversations=int(totals_row.conversations or 0),
            user_questions=int(totals_row.user_questions or 0),
            assistant_answers=int(totals_row.assistant_answers or 0),
            active_users=int(totals_row.active_users or 0),
            avg_confidence=_round(totals_row.avg_confidence),
            grounded_rate=_round(totals_row.grounded_rate),
            avg_latency_ms=int(totals_row.avg_latency_ms) if totals_row.avg_latency_ms is not None else None,
        ),
        per_product=[
            ProductAnalytics(
                product_id=row.product_id,
                product_name=row.product_name,
                conversations=int(row.conversations or 0),
                questions=int(row.questions or 0),
                avg_confidence=_round(row.avg_confidence),
                unanswered=int(row.unanswered or 0),
            )
            for row in product_rows
        ],
        knowledge_gaps=[
            KnowledgeGap(
                conversation_id=row.conversation_id,
                product_name=row.product_name,
                question=row.question or "(question unavailable)",
                answer_preview=row.answer_preview[:240],
                confidence=_round(row.confidence),
                created_at=row.created_at,
            )
            for row in gap_rows
        ],
        top_questions=[TopQuestion(question=row.question, count=int(row.count)) for row in question_rows],
    )


def _round(value: float | None, digits: int = 4) -> float | None:
    return round(float(value), digits) if value is not None else None


def _totals_stmt():
    return select(
        func.count(func.distinct(Conversation.id)).label("conversations"),
        func.count(func.distinct(Conversation.user_id)).label("active_users"),
        func.count(Message.id).filter(Message.role == MessageRole.USER).label("user_questions"),
        func.count(Message.id)
        .filter(Message.role == MessageRole.ASSISTANT)
        .label("assistant_answers"),
        func.avg(Message.confidence)
        .filter(Message.role == MessageRole.ASSISTANT, Message.confidence.is_not(None))
        .label("avg_confidence"),
        func.avg(case((Message.found_in_manual.is_(True), 1.0), else_=0.0))
        .filter(Message.role == MessageRole.ASSISTANT, Message.found_in_manual.is_not(None))
        .label("grounded_rate"),
        func.avg(Message.latency_ms)
        .filter(Message.role == MessageRole.ASSISTANT, Message.latency_ms.is_not(None))
        .label("avg_latency_ms"),
    ).join(Conversation, Message.conversation_id == Conversation.id)


def _per_product_stmt():
    return (
        select(
            Product.id.label("product_id"),
            Product.name.label("product_name"),
            func.count(func.distinct(Conversation.id)).label("conversations"),
            func.count(Message.id).filter(Message.role == MessageRole.USER).label("questions"),
            func.avg(Message.confidence)
            .filter(Message.role == MessageRole.ASSISTANT, Message.confidence.is_not(None))
            .label("avg_confidence"),
            func.count(Message.id)
            .filter(Message.role == MessageRole.ASSISTANT, Message.found_in_manual.is_(False))
            .label("unanswered"),
        )
        .outerjoin(Conversation, Conversation.product_id == Product.id)
        .outerjoin(Message, Message.conversation_id == Conversation.id)
        .group_by(Product.id, Product.name)
        .order_by(func.count(Message.id).desc())
    )


def _knowledge_gaps_stmt():
    assistant = aliased(Message)
    user_msg = aliased(Message)

    # The user question that produced each not-grounded answer.
    question_sq = (
        select(user_msg.content)
        .where(
            user_msg.conversation_id == assistant.conversation_id,
            user_msg.role == MessageRole.USER,
            user_msg.created_at <= assistant.created_at,
        )
        .order_by(user_msg.created_at.desc())
        .limit(1)
        .scalar_subquery()
        .correlate(assistant)
    )

    return (
        select(
            assistant.conversation_id,
            Conversation.product_name,
            question_sq.label("question"),
            assistant.content.label("answer_preview"),
            assistant.confidence,
            assistant.created_at,
        )
        .join(Conversation, Conversation.id == assistant.conversation_id)
        .where(
            assistant.role == MessageRole.ASSISTANT,
            assistant.found_in_manual.is_(False),
        )
        .order_by(assistant.created_at.desc())
        .limit(_GAP_LIMIT)
    )


def _top_questions_stmt():
    normalized = func.lower(func.btrim(Message.content))
    return (
        select(normalized.label("question"), func.count().label("count"))
        .where(
            Message.role == MessageRole.USER,
            func.length(Message.content) >= _MIN_QUESTION_LENGTH,
        )
        .group_by(normalized)
        .order_by(func.count().desc())
        .limit(_TOP_QUESTIONS)
    )