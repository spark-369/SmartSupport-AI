"""Incremental extraction of the ``answer`` field from a streamed JSON object.

Ollama's structured-output mode constrains decoding to the ``Answer`` JSON
schema but still emits the payload token-by-token. To stream the *answer
prose* to the client while it is being generated, raw JSON deltas are fed
through :class:`AnswerFieldStreamer`: it locates the ``"answer"`` key, then
progressively decodes the JSON string value and returns only the newly
decoded characters.

Escape sequences (``\\n``, ``\\uXXXX``, ``\\\\`` …) are handled by decoding
the longest valid prefix via ``json.loads`` and holding back incomplete
escape tails — no regex parsing of model prose anywhere; the complete
payload is still validated through ``Answer.model_validate_json`` by the
caller (this class is a transport concern for live streaming only).
"""

from __future__ import annotations

import json

_KEY = '"answer"'
_WHITESPACE = " \t\r\n"


class AnswerFieldStreamer:
    """Feeds accumulated JSON text; returns newly decoded ``answer`` prose."""

    def __init__(self) -> None:
        self._value_start: int | None = None  # offset right after the opening quote
        self._decoded = ""  # decoded value text already accounted for
        self._done = False  # closing quote seen

    def feed(self, buffer: str) -> str:
        """Process the full accumulated JSON so far; return the new text delta."""
        if self._done:
            return ""
        if self._value_start is None:
            self._value_start = _find_answer_value_start(buffer)
            if self._value_start is None:
                return ""
        raw = buffer[self._value_start :]

        end = _find_string_end(raw)
        candidate = raw if end is None else raw[:end]

        # Hold back a trailing run of backslashes: it may be a dangling escape
        # opener ('\n' split across deltas) or an escaped backslash ('\\') —
        # both resolve on a later feed, keeping the emitted text a stable prefix.
        run = 0
        while run < len(candidate) and candidate[len(candidate) - 1 - run] == "\\":
            run += 1
        if run and end is None:
            candidate = candidate[: len(candidate) - run]
        elif run and end is not None:
            # The closing quote was found; any backslash run before it is a
            # complete escape sequence (escape-aware scan guarantees this).
            pass

        decoded = _decode_prefix(candidate)
        if decoded is None:
            return ""
        if end is not None:
            self._done = True

        if decoded.startswith(self._decoded):
            delta = decoded[len(self._decoded) :]
            self._decoded = decoded
            return delta
        # Re-interpretation shrink (should not happen with run-holding) —
        # resync silently; the final answer event is authoritative anyway.
        self._decoded = decoded
        return ""


def _find_answer_value_start(buffer: str) -> int | None:
    """Offset just past the opening quote of the first ``"answer"`` value."""
    index = buffer.find(_KEY)
    if index == -1:
        return None
    cursor = index + len(_KEY)
    while cursor < len(buffer) and buffer[cursor] in _WHITESPACE:
        cursor += 1
    if cursor >= len(buffer) or buffer[cursor] != ":":
        return None  # not a key:value pattern (yet) — re-scan on the next feed
    cursor += 1
    while cursor < len(buffer) and buffer[cursor] in _WHITESPACE:
        cursor += 1
    if cursor >= len(buffer) or buffer[cursor] != '"':
        return None
    return cursor + 1


def _find_string_end(raw: str) -> int | None:
    """Index of the closing quote of a JSON string body (escape-aware)."""
    escaped = False
    for index, char in enumerate(raw):
        if escaped:
            escaped = False
        elif char == "\\":
            escaped = True
        elif char == '"':
            return index
    return None


def _decode_prefix(candidate: str) -> str | None:
    """Decode a JSON string body prefix; hold back incomplete escape tails."""
    for trim in range(0, 7):  # covers dangling '\\' and partial '\\uXXX' tails
        attempt = candidate[: len(candidate) - trim] if trim else candidate
        if not attempt:
            return ""
        try:
            return json.loads('"' + attempt + '"')
        except ValueError:
            continue
    return None