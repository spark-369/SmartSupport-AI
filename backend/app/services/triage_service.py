"""Ticket triage lifecycle: AI classification from support chat + escalation workflow."""

from __future__ import annotations

import re
import time
import uuid
from datetime import UTC, datetime

from sqlalchemy import case, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.errors import ConflictError, NotFoundError
from app.core.logging import get_logger
from app.models.enums import MessageRole, TicketStatus
from app.models.message import Message
from app.models.product import Product
from app.models.ticket import Ticket
from app.models.user import User
from app.schemas.ai import TicketTriage
from app.services import chat_service
from app.services.retrieval import retrieve

logger = get_logger("triage_service")

_URGENCY_RANK = case(
    (Ticket.urgency == "critical", 0),
    (Ticket.urgency == "high", 1),
    (Ticket.urgency == "medium", 2),
    else_=3,
)

# The actionable workload: open + escalated. Resolved/dismissed are archives.
_ACTIVE_STATUSES = Ticket.status.in_([TicketStatus.OPEN, TicketStatus.ESCALATED])


_REQUEST_VERB_PATTERN = re.compile(
    r"\b(?:please\s+)?"
    r"(?P<verb>give me|send|ship|deliver|bring|order|buy|replace|exchange|"
    r"refund|cancel|reschedule|escalate)\b\s*(?P<object>[^.!?\n]{0,80})",
    re.IGNORECASE,
)

# Customer request verb -> the fulfillment action the support team performs.
_SOLUTION_VERBS = {
    "give me": "deliver",
    "send": "deliver",
    "ship": "deliver",
    "deliver": "deliver",
    "bring": "deliver",
    "order": "order",
    "buy": "order",
    "replace": "replace",
    "exchange": "replace",
    "refund": "refund",
    "cancel": "cancel",
    "reschedule": "reschedule",
    "escalate": "escalate",
}


def _infer_requested_action(message: str) -> str | None:
    """Safety net for the 0.5B extractor: derive the SOLUTION action.

    The classifier often leaves ``requested_action`` null for short imperative
    requests ("give me sugar"). The queue needs the action the support team
    should take — not the customer's words — so the request verb is mapped to
    its fulfillment action ("deliver sugar", "replace the shirt"). How-to
    questions ("how do I cancel my subscription?") are informational — the
    guard skips them even when they contain a request verb.
    """
    match = _REQUEST_VERB_PATTERN.search(message)
    if match is None:
        return None
    prefix = message[: match.start()].rsplit(".", 1)[-1].rsplit("!", 1)[-1].rsplit("?", 1)[-1]
    if re.search(r"\b(how (do|to|can|about)|can i|where (do|is)|what (do|is))\b", prefix, re.IGNORECASE):
        return None
    verb = match.group("verb").lower()
    obj = match.group("object") or ""
    # "send me a replacement" / "cancel my order" -> fulfillment phrasing.
    obj = re.sub(r"^(me|us)\s+", "", obj, flags=re.IGNORECASE)
    obj = re.sub(r"^my\s+", "the ", obj, flags=re.IGNORECASE)
    obj = obj.strip().rstrip(".,!?:;").strip()
    action = f"{_SOLUTION_VERBS[verb]} {obj}".strip()
    return action[:120] or None


def _clean_topics(topics: list[str], category: str) -> list[str]:
    """Dedupe topics and drop category-slug noise the small model leaks in."""
    cleaned: list[str] = []
    for topic in topics:
        value = topic.strip().lower()
        if not value or "_" in value or value == category or value in cleaned:
            continue
        cleaned.append(value)
    return cleaned[:6]


async def create_ticket_from_conversation(
    session: AsyncSession,
    rag,
    embedder,
    user: User,
    conversation_id: uuid.UUID,
    message_id: uuid.UUID | None = None,
) -> Ticket:
    """Classify a customer message from a support chat and persist the ticket.

    The triaged message is the given user message, the user question preceding
    the given assistant answer, or — by default — the latest user message of
    the conversation. Product context comes from the conversation; when the
    product has ingested manuals, relevant excerpts are retrieved so the
    suggested reply can answer simple how-to questions instead of escalating.
    """
    conversation = await chat_service.get_conversation(session, user.id, conversation_id)
    source = await _resolve_source_message(session, conversation_id, message_id)

    product: Product | None = None
    if conversation.product_id is not None:
        product = await session.get(Product, conversation.product_id)

    # Ground the triage in the product's manuals when available.
    manual_context = []
    if product is not None:
        try:
            settings = get_settings()
            vector = await embedder.embed_query(source.content)
            manual_context = await retrieve(
                session,
                product.id,
                vector,
                top_k=3,
                min_score=settings.retrieval_min_score,
            )
        except Exception as exc:  # embedding/retrieval issues must not block triage
            logger.warning("Manual context retrieval failed for triage: %s", exc)
            manual_context = []

    started = time.perf_counter()
    triage: TicketTriage = await rag.analyze_ticket(
        source.content, conversation.product_name, manual_context
    )

    # Post-process the small model's extraction: fill a missing requested_action
    # from an explicit request verb, and strip category-slug noise from topics.
    extracted = triage.extracted_data
    if not extracted.requested_action:
        extracted.requested_action = _infer_requested_action(source.content)
    extracted.topics = _clean_topics(extracted.topics, triage.category)

    # Deterministic escalation decision: let the grounded-answer chain decide
    # whether the manuals resolve the question. A 0.5B classifier alone is too
    # unreliable for needs_human — the RAG answer (found_in_manual) is proof.
    needs_human = triage.needs_human
    urgency = triage.urgency
    escalation_reason = triage.escalation_reason
    if manual_context:
        try:
            answer = await rag.generate_answer(
                source.content, manual_context, conversation.product_name
            )
            if answer.found_in_manual:
                # The manuals resolve it — no human needed.
                needs_human = False
                urgency = "medium" if urgency in ("critical", "high") else urgency
            else:
                needs_human = True
                escalation_reason = triage.escalation_reason or (
                    "Not answerable from the available manuals."
                )
        except Exception as exc:  # answer pass failed — keep the classifier verdict
            logger.warning("Grounded-answer pass failed for triage: %s", exc)

    latency_ms = int((time.perf_counter() - started) * 1000)

    ticket = Ticket(
        created_by=user.id,
        conversation_id=conversation.id,
        source_message_id=source.id,
        product_id=product.id if product else None,
        product_name=conversation.product_name,
        raw_message=source.content,
        status=TicketStatus.OPEN,
        category=triage.category,
        urgency=urgency,
        sentiment=triage.sentiment,
        needs_human=needs_human,
        # Guard: an escalation without a reason is useless in the queue.
        escalation_reason=escalation_reason
        or ("Flagged for human review." if needs_human else None),
        summary=triage.summary,
        extracted_data=triage.extracted_data.model_dump(),
        triage_latency_ms=latency_ms,
    )
    session.add(ticket)
    await session.commit()
    await session.refresh(ticket)
    return ticket


async def _resolve_source_message(
    session: AsyncSession, conversation_id: uuid.UUID, message_id: uuid.UUID | None
) -> Message:
    if message_id is not None:
        message = await session.get(Message, message_id)
        if message is None or message.conversation_id != conversation_id:
            raise NotFoundError("Message not found.")
        if message.role == MessageRole.USER:
            return message
        # An assistant answer was escalated — triage the question before it.
        result = await session.execute(
            select(Message)
            .where(
                Message.conversation_id == conversation_id,
                Message.role == MessageRole.USER,
                Message.created_at <= message.created_at,
            )
            .order_by(Message.created_at.desc())
            .limit(1)
        )
        user_message = result.scalar_one_or_none()
        if user_message is None:
            raise ConflictError("This answer has no customer question to triage.")
        return user_message

    messages = await chat_service.get_messages(session, conversation_id)
    user_messages = [m for m in messages if m.role == MessageRole.USER]
    if not user_messages:
        raise ConflictError("This conversation has no customer message to triage yet.")
    return user_messages[-1]


async def list_tickets(
    session: AsyncSession,
    user: User,
    *,
    status: TicketStatus | None = None,
    needs_human: bool | None = None,
    product_id: uuid.UUID | None = None,
    urgency: str | None = None,
    search: str | None = None,
) -> list[Ticket]:
    """Queue for the caller — admins see the whole desk, users see their own.

    Ordered by urgency rank, then newest first (a triage queue is work-ordered,
    not time-ordered). The default view is the ACTIVE workload (open + escalated);
    resolved and dismissed tickets appear only when explicitly filtered.
    """
    stmt = select(Ticket, User.full_name.label("creator_name")).join(
        User, Ticket.created_by == User.id, isouter=True
    )
    if user.role != "admin":
        stmt = stmt.where(Ticket.created_by == user.id)
    if status is not None:
        stmt = stmt.where(Ticket.status == status)
    else:
        stmt = stmt.where(_ACTIVE_STATUSES)
    if needs_human is not None:
        stmt = stmt.where(Ticket.needs_human == needs_human)
        if status is None:
            # "Needs human" is an actionable view — resolved ones drop out too.
            stmt = stmt.where(_ACTIVE_STATUSES)
    if product_id is not None:
        stmt = stmt.where(Ticket.product_id == product_id)
    if urgency is not None:
        stmt = stmt.where(Ticket.urgency == urgency)
    if search is not None and search.strip():
        # Spaces become '_' — in ILIKE that is a single-char wildcard, so
        # "complaint exchange" also matches the stored "complaint_exchange".
        pattern = f"%{search.strip().replace(' ', '_')}%"
        stmt = stmt.where(
            or_(
                Ticket.raw_message.ilike(pattern),
                Ticket.summary.ilike(pattern),
                Ticket.category.ilike(pattern),
            )
        )
    stmt = stmt.order_by(_URGENCY_RANK, Ticket.created_at.desc()).limit(100)

    tickets: list[Ticket] = []
    for ticket, creator_name in (await session.execute(stmt)).all():
        setattr(ticket, "created_by_name", creator_name)
        tickets.append(ticket)
    return tickets


async def get_ticket_for_user(session: AsyncSession, ticket_id: uuid.UUID, user: User) -> Ticket:
    ticket = await session.get(Ticket, ticket_id)
    if ticket is None:
        raise NotFoundError("Ticket not found.")
    if user.role != "admin" and ticket.created_by != user.id:
        raise NotFoundError("Ticket not found.")  # do not leak existence
    if ticket.created_by is not None:
        creator = await session.get(User, ticket.created_by)
        setattr(ticket, "created_by_name", creator.full_name if creator else None)
    else:
        setattr(ticket, "created_by_name", None)
    return ticket


async def update_status(
    session: AsyncSession, ticket: Ticket, new_status: TicketStatus, note: str | None, actor: User
) -> Ticket:
    ticket.status = new_status
    if new_status == TicketStatus.RESOLVED:
        ticket.resolved_at = datetime.now(UTC)
        ticket.resolved_by = actor.id
        ticket.resolution_note = note
    elif new_status == TicketStatus.DISMISSED:
        ticket.resolution_note = note
    else:  # reopened / escalated — clear resolution bookkeeping
        ticket.resolved_at = None
        ticket.resolved_by = None
        ticket.resolution_note = note
    await session.commit()
    await session.refresh(ticket)
    return ticket


async def queue_counts(session: AsyncSession, user: User) -> dict[str, int]:
    """Counters for the queue tabs + stat strip (scoped like list_tickets).

    ``active`` counts the actionable workload (open + escalated); ``needs_human``
    and the urgency keys are scoped to that active workload too. ``resolved``
    and ``dismissed`` are archive counters.
    """
    base = select(func.count()).select_from(Ticket)
    if user.role != "admin":
        base = base.where(Ticket.created_by == user.id)

    async def count(*conditions) -> int:
        stmt = base
        if conditions:
            stmt = stmt.where(*conditions)
        return int(await session.scalar(stmt) or 0)

    return {
        "active": await count(_ACTIVE_STATUSES),
        "open": await count(Ticket.status == TicketStatus.OPEN),
        "escalated": await count(Ticket.status == TicketStatus.ESCALATED),
        "resolved": await count(Ticket.status == TicketStatus.RESOLVED),
        "dismissed": await count(Ticket.status == TicketStatus.DISMISSED),
        "needs_human": await count(Ticket.needs_human.is_(True), _ACTIVE_STATUSES),
        "critical": await count(Ticket.urgency == "critical", _ACTIVE_STATUSES),
        "high": await count(Ticket.urgency == "high", _ACTIVE_STATUSES),
        "medium": await count(Ticket.urgency == "medium", _ACTIVE_STATUSES),
        "low": await count(Ticket.urgency == "low", _ACTIVE_STATUSES),
    }