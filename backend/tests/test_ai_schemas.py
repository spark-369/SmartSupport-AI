"""Structured-output schema validation tests."""

from __future__ import annotations

import json

import pytest
from pydantic import ValidationError

from app.schemas.ai import Answer, ConversationTitle, QueryRewrite, SourceRef


def test_query_rewrite_defaults():
    rewrite = QueryRewrite(rewritten_query="descale coffee machine")
    assert rewrite.keywords == []


def test_answer_bounds():
    with pytest.raises(ValidationError):
        Answer(
            answer="x",
            confidence=1.5,  # out of range
            found_in_manual=True,
        )


def test_answer_accepts_model_json():
    raw = json.dumps(
        {
            "answer": "Descale every 3 months.",
            "confidence": 0.9,
            "found_in_manual": True,
            "cited_excerpts": [1],
            "follow_up_questions": ["How?", "When?"],
        }
    )
    answer = Answer.model_validate_json(raw)
    assert answer.cited_excerpts == [1]
    assert len(answer.follow_up_questions) == 2


def test_answer_defaults_to_uncited():
    answer = Answer(answer="Not in the manual.", confidence=0.2, found_in_manual=False)
    assert answer.cited_excerpts == []


def test_source_ref_score_bounds():
    with pytest.raises(ValidationError):
        SourceRef(chunk_id="a", document_name="d", quote="q", score=-2.0)


def test_title_limits():
    with pytest.raises(ValidationError):
        ConversationTitle(title="x" * 81)
