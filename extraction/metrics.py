"""Deterministic extraction metrics (no LLM judge).

Compares an extractor's raw output + serialized state against the gold
standard (extraction/gold.py). Every matcher is a pure string/regex check.

Matchers:
  exact      — the exact token is present verbatim in raw output
  word       — the token appears as a whole word (regex \\b)
  structural — all component tokens present in the serialized state
  negative   — the design-relevant token is co-located with a negation
               ("do not/not implement/not write") in raw output
  temporal   — a temporal-scope marker ("next session / later / future")
               is present in raw output
"""

from __future__ import annotations

import re

from extraction.gold import CATEGORIES, GOLD


def check_fact(fact: dict, raw: str, serialized: str) -> bool:
    m = fact["match"]
    v = fact["value"]
    if m == "exact":
        return v in raw
    if m == "word":
        return bool(re.search(rf"\b{re.escape(v)}\b", raw))
    if m == "structural":
        return all(tok in serialized for tok in v)
    if m == "negative":
        # token present AND a negation within a bounded window
        idx = raw.find(v)
        if idx < 0:
            return False
        window = raw[max(0, idx - 80): idx + 80].lower()
        return any(neg in window for neg in
                   ("do not", "not implement", "not write", "don't", "deferred",
                    "not now", "not add", "not yet"))
    if m == "temporal":
        low = raw.lower()
        return any(t in low for t in
                   ("next session", "future session", "later", "next working",
                    "implementation time", "provided at"))
    raise ValueError(f"unknown matcher {m}")


def evaluate_extraction(benchmark: str, raw: str, serialized: str,
                        parse_ok: bool, schema_valid: bool) -> dict:
    """Return per-category recall + counts for ONE extraction."""
    facts = GOLD[benchmark]["facts"]
    out: dict = {"benchmark": benchmark, "parse_ok": parse_ok,
                 "schema_valid": schema_valid}
    # If it didn't parse, recall categories are undefined (None): parse_rate
    # carries the failure dimension separately; recall is "of successfully
    # parsed extractions" only.
    if not parse_ok:
        for cat in CATEGORIES:
            out[f"{cat}_recall"] = None
            out[f"{cat}_n"] = 0
        out["overall_recall"] = None
        return out

    per_cat: dict[str, list[bool]] = {c: [] for c in CATEGORIES}
    for f in facts:
        per_cat[f["type"]].append(check_fact(f, raw, serialized))

    for cat in CATEGORIES:
        hits = per_cat[cat]
        out[f"{cat}_n"] = len(hits)
        # Categories with no gold facts are absent (None), not 100%.
        if hits:
            out[f"{cat}_recall"] = sum(hits) / len(hits)
        else:
            out[f"{cat}_recall"] = None

    all_hits = [h for cat in CATEGORIES for h in per_cat[cat]]
    out["overall_recall"] = sum(all_hits) / len(all_hits) if all_hits else None
    return out


def aggregate(per_extraction: list[dict], benchmark: str | None = None) -> dict:
    """Aggregate a list of evaluate_extraction() results into means."""
    rows = [r for r in per_extraction
            if benchmark is None or r["benchmark"] == benchmark]
    n = len(rows)
    if n == 0:
        return {"n": 0}
    sum_fields = {f"{c}_recall" for c in CATEGORIES} | {"overall_recall"}
    agg = {"n": n,
           "parse_rate": sum(1 for r in rows if r["parse_ok"]) / n,
           "schema_rate": sum(1 for r in rows if r["schema_valid"]) / n}
    for f in sum_fields:
        vals = [r[f] for r in rows if r.get(f) is not None]
        agg[f] = (sum(vals) / len(vals)) if vals else None
    return agg