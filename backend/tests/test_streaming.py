"""Unit tests for the incremental answer-field streamer (pure logic)."""

from __future__ import annotations

import json

from app.services.rag.streaming import AnswerFieldStreamer


def _payload(answer: str) -> str:
    """A realistic schema-ordered payload (answer first)."""
    return json.dumps(
        {
            "answer": answer,
            "confidence": 0.87,
            "found_in_manual": True,
            "cited_excerpts": [1, 3],
            "follow_up_questions": ["How often?", "Why?"],
        }
    )


def _streamed(text: str, chunk_size: int = 5) -> str:
    """Feed ``text`` in fixed-size chunks; return the concatenated deltas."""
    streamer = AnswerFieldStreamer()
    buffer = ""
    out = ""
    for start in range(0, len(text), chunk_size):
        buffer += text[start : start + chunk_size]
        out += streamer.feed(buffer)
    return out


def test_complete_payload_single_feed():
    streamer = AnswerFieldStreamer()
    delta = streamer.feed(_payload("Descale every 3 months."))
    assert delta == "Descale every 3 months."
    assert streamer.feed(_payload("Descale every 3 months.")) == ""  # done → no more


def test_char_by_char_streaming_concatenates_to_full_answer():
    answer = "Rinse the water tank, then plug in the machine."
    assert _streamed(_payload(answer), chunk_size=1) == answer


def test_escaped_newlines_and_quotes_are_decoded():
    answer = 'Step 1:\nRinse the tank.\nSay "ready" when done.'
    assert _streamed(_payload(answer), chunk_size=3) == answer


def test_unicode_escapes_decode():
    answer = "Café créma — 92°C."
    payload = json.dumps({"answer": answer}, ensure_ascii=False)
    assert _streamed(payload, chunk_size=2) == answer

    payload_ascii = json.dumps({"answer": answer}, ensure_ascii=True)  # \u00e9 escapes
    assert _streamed(payload_ascii, chunk_size=4) == answer


def test_split_escape_sequence_is_held_back():
    streamer = AnswerFieldStreamer()
    payload = '{"answer": "A\\nB", "confidence": 0.5}'  # raw: A\nB
    # Feed up to and including the backslash → nothing unsafe emitted yet.
    buffer = ""
    out = ""
    for char in payload:
        buffer += char
        out += streamer.feed(buffer)
    assert out == "A\nB"


def test_answer_key_found_after_other_fields():
    payload = json.dumps({"confidence": 0.5, "answer": "Later field"})
    assert _streamed(payload, chunk_size=6) == "Later field"


def test_missing_answer_key_emits_nothing():
    streamer = AnswerFieldStreamer()
    assert streamer.feed('{"confidence": 0.9, "found_in_manual": false}') == ""
    assert streamer.feed('{"confidence": 0.9}') == ""


def test_empty_answer_value():
    assert _streamed('{"answer": "", "confidence": 0.5}', chunk_size=3) == ""


def test_prefix_never_retracts_midstream():
    """Emitted text must always be a prefix of the final decoded value."""
    answer = "Line one.\nLine two with \\ backslash."
    payload = _payload(answer)
    streamer = AnswerFieldStreamer()
    buffer = ""
    emitted = ""
    for char in payload:
        buffer += char
        delta = streamer.feed(buffer)
        assert answer.startswith(emitted)
        emitted += delta
    assert emitted == answer
