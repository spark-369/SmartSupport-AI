"""Structured-output schemas for Ollama native JSON mode.

Each schema is passed to the model via ``format=Schema.model_json_schema()``
(constrained decoding) and validated with ``Schema.model_validate_json`` —
no manual/regex JSON parsing anywhere.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class QueryRewrite(BaseModel):
    """Stage-1 output: a self-contained search query for retrieval."""

    rewritten_query: str = Field(
        min_length=1,
        max_length=400,
        description="Standalone search query with context resolved (pronouns expanded).",
    )
    keywords: list[str] = Field(default_factory=list, max_length=8)


class SourceRef(BaseModel):
    """A retrieved manual excerpt cited in an answer."""

    chunk_id: str
    document_name: str
    quote: str = Field(max_length=240)
    score: float = Field(ge=-1.0, le=1.0)
    page: int | None = None


class Answer(BaseModel):
    """Stage-2 output: the final grounded answer.

    The model cites excerpts **by number only** — quotes/scores/pages are
    resolved server-side from the retrieved chunks. This keeps the generated
    JSON small (a 0.5B model cannot afford to echo 240-char quotes × 5
    sources within its token budget) and guarantees source consistency.
    """

    answer: str = Field(min_length=1, max_length=4000)
    confidence: float = Field(ge=0.0, le=1.0)
    found_in_manual: bool = Field(description="True only when the manual excerpts support the answer.")
    cited_excerpts: list[int] = Field(
        default_factory=list,
        max_length=10,
        description="1-based numbers of the MANUAL EXCERPTS actually used, e.g. [1, 3].",
    )
    follow_up_questions: list[str] = Field(default_factory=list, max_length=3)


class ConversationTitle(BaseModel):
    """Stage-3 output: a short conversation title."""

    title: str = Field(min_length=1, max_length=80)


# ---------------------------------------------------------------------------
# Ticket triage (support-desk classification & escalation)
# ---------------------------------------------------------------------------

TicketCategory = Literal[
    "complaint_exchange",
    "complaint_refund",
    "technical_issue",
    "how_to_question",
    "shipping_logistics",
    "billing_payment",
    "warranty_claim",
    "general_inquiry",
    "feedback",
]
TicketUrgency = Literal["low", "medium", "high", "critical"]
TicketSentiment = Literal["satisfied", "neutral", "concerned", "frustrated", "angry"]


class TicketExtracted(BaseModel):
    """Facts extracted from the customer message (null when not present)."""

    product: str | None = Field(default=None, max_length=120, description="Product the message is about, if identifiable.")
    issue: str | None = Field(default=None, max_length=400, description="The core problem or request in one sentence.")
    requested_action: str | None = Field(
        default=None,
        max_length=200,
        description=(
            "The solution action the support team should take to resolve the issue, e.g. "
            "'deliver the missing sugar', 'send a replacement unit', 'process a refund'. "
            "An action, not the customer's complaint. Null only for pure informational questions."
        ),
    )
    topics: list[str] = Field(default_factory=list, max_length=6, description="Up to 6 short keywords/topics.")


class TicketTriage(BaseModel):
    """Structured triage of a customer message.

    Goes beyond the baseline (category / urgency / sentiment / extracted data /
    needs_human) with an escalation reason and a one-line summary. Whether the
    manuals can answer the question is decided deterministically by the
    grounded-answer pass in the service layer — not by the classifier.
    """

    category: TicketCategory
    urgency: TicketUrgency
    sentiment: TicketSentiment
    extracted_data: TicketExtracted
    needs_human: bool = Field(description="True when a human agent must take over.")
    escalation_reason: str | None = Field(default=None, max_length=400, description="Why a human is needed (required when needs_human).")
    summary: str = Field(min_length=1, max_length=300, description="One-sentence TL;DR of the ticket.")
