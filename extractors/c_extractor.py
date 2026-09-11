"""Condition C extractor: transcript -> raw extractor output.

Frozen rules:
- Extraction model: shared with B (continuity.extraction), same
  model/temperature/top_p/max_tokens.
- Prompt: fixed (below), v1. Never mentions the experiment.
- Input: serialized session transcript (role: content lines).
- Output handling: raw output is ALWAYS saved. Parsing tries:
  (1) direct json.loads, (2) outermost {...} block. On failure the
  error is recorded and NO repair is attempted — garbage is recorded
  as garbage; we do not hand-curate C.

The extractor is an interface seam for offline tests: pass a fake
`llm_complete` callable to run without any network.
"""

from __future__ import annotations

import json
import os
import re
from typing import Callable

from continuity.extraction import (
    EXTRACTOR_MAX_TOKENS,
    EXTRACTOR_MODEL,
    EXTRACTOR_TEMPERATURE,
    EXTRACTOR_TOP_P,
)

PROMPT_VERSION = "c-extraction-v1"

SYSTEM_PROMPT = """You are a continuity-state extractor.

Given a session transcript of a software engineering agent, extract the
durable project state that a future session would need, using EXACTLY
this JSON shape (schema C-v0.1):

{
  "goals":        [{"id": "...", "description": "..."}],
  "tasks":        [{"id": "...", "description": "...", "status": "...", "files": ["..."]}],
  "decisions":    [{"id": "...", "decision": "...", "reason": "...", "status": "active"}],
  "entities":     [{"id": "...", "name": "...", "type": "...", "description": "..."}],
  "facts":        [{"id": "...", "fact": "..."}],
  "events":       [{"id": "...", "event": "...", "session": 1}],
  "failures":     [{"id": "...", "signature": "...", "description": "...", "status": "..."}],
  "dependencies": [{"id": "...", "description": "..."}],
  "current_state": {"branch": "...", "implemented_features": ["..."],
                    "known_bugs": ["..."], "tests_status": "...",
                    "active_work": "..."}
}

Rules:
- Extract only information explicitly supported by the transcript.
- Do not infer undocumented facts. Do not invent decisions.
- Do not provide advice. Do not describe the extraction process.
- Use stable IDs: G-001, TASK-001, DEC-001, E-001, F-001, EV-001,
  FAIL-001, DEP-001, numbered in order of appearance.
- Return ONLY the JSON object."""


class ExtractionError(Exception):
    """Recorded, never repaired."""


class ExtractionTransportError(ExtractionError):
    """Transport-level extractor failure after all retries (AMD-001).
    Distinct from parse failure; never confused with content issues."""


# Amendment AMD-001: bounded retry for transient transport failures only.
# Parse failures are NOT retried (see parse_output / ExtractionError).
_TRANSPORT_MAX_ATTEMPTS = 3


def _is_transient(exc: Exception) -> bool:
    """Only transport-level failures may be retried (AMD-001): HTTP 5xx,
    timeout, connection errors, rate/congestion signals."""
    try:
        from openai import (
            APIConnectionError,
            APIStatusError,
            APITimeoutError,
        )
    except Exception:  # openai always installed in our env
        return False
    if isinstance(exc, (APITimeoutError, APIConnectionError)):
        return True
    if isinstance(exc, APIStatusError):
        return exc.status_code is None or exc.status_code >= 500 or exc.status_code == 429
    return False


def _default_llm_complete(system: str, user: str) -> str:
    from openai import OpenAI

    client = OpenAI(
        api_key=os.environ.get("LLM_API_KEY"),
        base_url=os.environ.get("LLM_BASE_URL") or None,
        timeout=600.0,
    )
    last_err: Exception | None = None
    for attempt in range(1, _TRANSPORT_MAX_ATTEMPTS + 1):
        try:
            resp = client.chat.completions.create(
                model=EXTRACTOR_MODEL,
                temperature=EXTRACTOR_TEMPERATURE,
                top_p=EXTRACTOR_TOP_P,
                max_tokens=EXTRACTOR_MAX_TOKENS,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
            )
            _EXTRACT_TELEMETRY["attempt"] = attempt
            return resp.choices[0].message.content or ""
        except Exception as e:  # noqa: BLE001 - classified below
            last_err = e
            if not _is_transient(e):
                raise
    raise ExtractionTransportError(
        f"extractor transport failed after {_TRANSPORT_MAX_ATTEMPTS} attempts: {last_err}"
    )


# Module-level telemetry for the in-flight extraction (single-threaded
# harness; populated by _default_llm_complete, read by extract_c_state).
_EXTRACT_TELEMETRY: dict = {"attempt": 0}


def serialize_transcript(messages: list[dict]) -> str:
    lines = []
    for m in messages:
        content = str(m.get("content", ""))
        if len(content) > 4000:  # fixed input guard, same for B chunks?
            content = content[:4000] + " ...[truncated]"
        lines.append(f"[{m.get('role', '?')}] {content}")
    return "\n\n".join(lines)


def parse_output(raw: str) -> dict:
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        m = re.search(r"\{.*\}", raw, re.DOTALL)
        if m:
            try:
                return json.loads(m.group(0))
            except json.JSONDecodeError:
                pass
    raise ExtractionError("extractor output is not parseable JSON")


def schema_is_valid(state: dict) -> bool:
    """AMD-002: hard schema check used by bounded recovery. The frozen schema
    requires schema_version=C-v0.1 and all ten top-level keys present."""
    required = {"schema_version", "goals", "tasks", "decisions", "entities",
                "facts", "events", "failures", "dependencies", "current_state"}
    return (
        isinstance(state, dict)
        and state.get("schema_version") == "C-v0.1"
        and required.issubset(state.keys())
        and isinstance(state.get("current_state"), dict)
    )


_MAX_RECOVERY_ATTEMPTS = 3
_RECOVERY_TELEMETRY: dict = {}


def extract_c_state(
    messages: list[dict],
    llm_complete: Callable[[str, str], str] | None = None,
) -> tuple[dict, str]:
    """Returns (state, raw_output). Raises ExtractionError on garbage.

    AMD-002 — bounded parse/schema recovery:
      up to _MAX_RECOVERY_ATTEMPTS total attempts, retrying ONLY on
      transport failure (AMD-001), malformed JSON, or schema-invalid output.
      Semantic fidelity (missing facts, paraphrase) NEVER triggers retry —
      that is a property of the extractor we are measuring, not fixing.

    Every attempt is recorded in _RECOVERY_TELEMETRY.
    """
    complete = llm_complete or _default_llm_complete
    _EXTRACT_TELEMETRY["attempt"] = 0
    USER = "SESSION TRANSCRIPT:\n\n" + serialize_transcript(messages)

    attempts = []
    last_raw = ""
    last_err: Exception | None = None
    for attempt in range(1, _MAX_RECOVERY_ATTEMPTS + 1):
        try:
            raw = complete(SYSTEM_PROMPT, USER)
            last_raw = raw
            state = normalize_state(parse_output(raw))
            ok = schema_is_valid(state)
            attempts.append({
                "attempt": attempt,
                "parse_success": True,
                "schema_valid": ok,
            })
            if not ok:
                last_err = ExtractionError(
                    "extractor output parsed but failed schema validation"
                )
                continue
            _RECOVERY_TELEMETRY.clear()
            _RECOVERY_TELEMETRY.update({
                "attempts": attempts,
                "attempt_count": attempt,
                "first_attempt_parse_success": attempts[0]["parse_success"],
                "final_parse_success": True,
                "final_schema_valid": True,
                "recovery_mode": "bounded_parse_schema_recovery (AMD-002)",
            })
            return state, raw
        except ExtractionTransportError as e:
            attempts.append({"attempt": attempt, "parse_success": False,
                             "schema_valid": False, "transport_error": str(e)})
            last_err = e
            break  # transport layer already retried (AMD-001); no point looping
        except ExtractionError as e:
            attempts.append({"attempt": attempt, "parse_success": False,
                             "schema_valid": False, "error": str(e)})
            last_err = e
    _RECOVERY_TELEMETRY.clear()
    _RECOVERY_TELEMETRY.update({
        "attempts": attempts,
        "attempt_count": len(attempts),
        "first_attempt_parse_success": attempts[0]["parse_success"],
        "final_parse_success": False,
        "recovery_mode": "bounded_parse_schema_recovery (AMD-002)",
    })
    raise ExtractionError(
        f"extraction failed after {len(attempts)} attempts: {last_err}"
    )


def normalize_state(parsed: dict) -> dict:
    """Coerce into the frozen schema shape. Missing categories become
    empty; this is normalization, not content repair."""
    if not isinstance(parsed, dict):
        raise ExtractionError("extractor output is not a JSON object")
    state = {
        "schema_version": "C-v0.1",
        "goals": [], "tasks": [], "decisions": [], "entities": [],
        "facts": [], "events": [], "failures": [], "dependencies": [],
        "current_state": {},
    }
    for key in state:
        if key == "schema_version":
            continue
        value = parsed.get(key)
        if value is None:
            continue
        if key == "current_state":
            if isinstance(value, dict):
                state[key] = value
            continue
        if isinstance(value, list):
            state[key] = [x for x in value if isinstance(x, dict)]
    return state


def extractor_identity() -> dict:
    return {
        "model": EXTRACTOR_MODEL,
        "temperature": EXTRACTOR_TEMPERATURE,
        "top_p": EXTRACTOR_TOP_P,
        "max_tokens": EXTRACTOR_MAX_TOKENS,
        "prompt_version": PROMPT_VERSION,
        "transport_max_attempts": _TRANSPORT_MAX_ATTEMPTS,
        "transport_attempt_used": _EXTRACT_TELEMETRY.get("attempt", 0),
        "recovery_telemetry": dict(_RECOVERY_TELEMETRY),
    }
