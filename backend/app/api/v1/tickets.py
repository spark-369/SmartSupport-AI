"""Ticket triage endpoints: queue, detail, workflow (creation happens from support chat)."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Query

from app.api.deps import CurrentUser, DbSession
from app.models.enums import TicketStatus
from app.schemas.ticket import TicketPublic, TicketStatusUpdate
from app.services import triage_service

router = APIRouter(prefix="/tickets", tags=["tickets"])


@router.get("", response_model=list[TicketPublic])
async def list_tickets(
    user: CurrentUser,
    db: DbSession,
    status_filter: TicketStatus | None = Query(None, alias="status"),
    needs_human: bool | None = None,
    product_id: uuid.UUID | None = None,
    urgency: str | None = None,
    search: str | None = None,
) -> list[TicketPublic]:
    """The triage queue — admins see the whole desk, users see their own tickets.

    Filters: status, needs_human, product, urgency and a text ``search`` over
    the raw message / summary / category.
    """
    tickets = await triage_service.list_tickets(
        db,
        user,
        status=status_filter,
        needs_human=needs_human,
        product_id=product_id,
        urgency=urgency,
        search=search,
    )
    return [TicketPublic.model_validate(t) for t in tickets]


@router.get("/counts")
async def ticket_counts(user: CurrentUser, db: DbSession) -> dict[str, int]:
    """Per-status counters for the queue filter tabs."""
    return await triage_service.queue_counts(db, user)


@router.get("/{ticket_id}", response_model=TicketPublic)
async def get_ticket(ticket_id: uuid.UUID, user: CurrentUser, db: DbSession) -> TicketPublic:
    ticket = await triage_service.get_ticket_for_user(db, ticket_id, user)
    return TicketPublic.model_validate(ticket)


@router.patch("/{ticket_id}", response_model=TicketPublic)
async def update_ticket_status(
    ticket_id: uuid.UUID,
    payload: TicketStatusUpdate,
    user: CurrentUser,
    db: DbSession,
) -> TicketPublic:
    """Move a ticket through the escalation workflow (owner or admin)."""
    ticket = await triage_service.get_ticket_for_user(db, ticket_id, user)
    updated = await triage_service.update_status(db, ticket, payload.status, payload.resolution_note, user)
    return TicketPublic.model_validate(updated)