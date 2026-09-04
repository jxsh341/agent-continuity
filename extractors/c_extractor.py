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


def _default_llm_complete(system: str, user: str) -> str:
    from openai import OpenAI

    client = OpenAI(
        api_key=os.environ.get("LLM_API_KEY"),
        base_url=os.environ.get("LLM_BASE_URL") or None,
        timeout=600.0,
    )
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
    return resp.choices[0].message.content or ""


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


def extract_c_state(
    messages: list[dict],
    llm_complete: Callable[[str, str], str] | None = None,
) -> tuple[dict, str]:
    """Returns (state, raw_output). Raises ExtractionError on garbage."""
    complete = llm_complete or _default_llm_complete
    raw = complete(SYSTEM_PROMPT, "SESSION TRANSCRIPT:\n\n" + serialize_transcript(messages))
    state = normalize_state(parse_output(raw))
    return state, raw


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
    }
