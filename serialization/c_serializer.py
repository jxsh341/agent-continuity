"""Deterministic C serializer: structured state -> context text.

Rules (frozen, deterministic):
- Header fixed.
- Categories rendered in the frozen truncation_priority order
  (see schemas/c_v0_1.json); current_state is its own section.
- Within a category, items render in stored order via fixed field order.
- Ordering/whitespace are fully determined by the state content.
- Truncation: per-item, in priority order, recorded.

Pure functions only — no LLM, no clock, no randomness.
"""

from __future__ import annotations

import json
from pathlib import Path

from continuity.tokens import TOKENIZER_ID, count_tokens

_SCHEMA = json.loads(
    (Path(__file__).parent.parent / "schemas" / "c_v0_1.json").read_text()
)
PRIORITY: list[str] = _SCHEMA["truncation_priority"]
FIELD_ORDER: dict[str, list[str]] = _SCHEMA["record_fields"]
CURRENT_STATE_FIELDS: list[str] = _SCHEMA["current_state_fields"]

HEADER = "Previous session state:"


def _fmt_scalar(v) -> str:
    if isinstance(v, list):
        return ", ".join(str(x) for x in v)
    return str(v)


def render_record(category: str, record: dict, index: int) -> str:
    fields = FIELD_ORDER[category]
    parts = []
    for f in fields:
        if f in record and record[f] not in (None, "", []):
            parts.append(str(record[f]) if f == fields[0] else f"{f}={_fmt_scalar(record[f])}")
    return f"{index}. " + "; ".join(parts)


def render_current_state(cs: dict) -> list[str]:
    lines = []
    for f in CURRENT_STATE_FIELDS:
        if f in cs and cs[f] not in (None, "", []):
            lines.append(f"- {f}: {_fmt_scalar(cs[f])}")
    return lines


def section_lines(state: dict, category: str) -> list[str]:
    if category == "current_state":
        cs = render_current_state(state.get("current_state") or {})
        return ["CURRENT STATE"] + cs if cs else []
    items = state.get(category)
    if not items:
        return []
    lines = [category.upper()]
    lines.extend(render_record(category, r, i) for i, r in enumerate(items, 1))
    return lines


def serialize_full(state: dict) -> str:
    sections: list[str] = []
    for cat in PRIORITY:
        lines = section_lines(state, cat)
        if lines:
            sections.append("\n".join(lines))
    body = "\n\n".join(sections)
    return HEADER + ("\n\n" + body if body else "")


def serialize_within_budget(state: dict, budget_tokens: int) -> tuple[str, dict]:
    """Deterministic truncation in frozen priority order.

    Returns (text, truncation_report). Item-wise truncation within the
    current section; whole sections that no longer fit are dropped.
    """
    full = serialize_full(state)
    before = count_tokens(full)
    report = {
        "schema_version": "C-v0.1",
        "tokenizer": TOKENIZER_ID,
        "tokens_before_budget": before,
        "serialized_tokens": before,
        "budget": budget_tokens,
        "truncated": False,
        "categories_present": [c for c in PRIORITY if section_lines(state, c)],
        "categories_truncated": [],
    }
    if before <= budget_tokens:
        return full, report

    # Deterministic drop: iterate categories in priority order; keep
    # items while they fit the remaining budget.
    used = count_tokens(HEADER)
    out_sections: list[str] = []
    present: list[str] = []
    truncated: list[str] = []
    for cat in PRIORITY:
        lines = section_lines(state, cat)
        if not lines:
            continue
        head, items = lines[0], lines[1:]
        kept = []
        if used + count_tokens(head) + 1 > budget_tokens:
            truncated.append(cat)  # no room even for its header
            continue
        local = used + count_tokens(head) + 1
        for line in items:
            n = count_tokens(line) + 1
            if local + n > budget_tokens:
                break
            kept.append(line)
            local += n
        if kept:
            out_sections.append("\n".join([head, *kept]))
            used = local
            present.append(cat)
            if len(kept) < len(items):
                truncated.append(cat)
        else:
            truncated.append(cat)
    text = HEADER + ("\n\n" + "\n\n".join(out_sections) if out_sections else "")
    report.update(
        serialized_tokens=count_tokens(text),
        truncated=True,
        categories_present=present,
        categories_truncated=truncated,
    )
    return text, report
