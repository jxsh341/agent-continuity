"""Extractor Reliability Study (exploratory; separate from Stage 1A).

Uses the FROZEN Stage 1A S1 transcripts as fixed inputs. For each benchmark,
runs the frozen nemotron extractor `N` times against a fixed transcript and
measures: JSON parse success, structured-state schema validity, critical-fact
recall, exact-token fidelity, serialized token size, and failure category.

NOT part of the A/B/C/D score. Does not change C schema/prompt/serializer,
benchmarks, or Stage 1A results.

Usage:
    .venv\\Scripts\\python scripts\\extractor_reliability.py [N]
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from benchmark.registry import BENCHMARKS  # noqa: E402
from extractors.c_extractor import (  # noqa: E402
    ExtractionError,
    extract_c_state,
)
from serialization.c_serializer import serialize_full  # noqa: E402
from continuity.tokens import count_tokens  # noqa: E402

# Ground-truth critical facts whose preservation we measure. "exact" tokens must
# appear verbatim; "structural" must be non-paraphrased components.
GROUND_TRUTH = {
    "fastapi": {
        "exact": ["/reports/summary", "page_size", "reports"],
        "value": "7",
        "structural": ["category", "count"],
    },
    "schema_migration": {
        "exact": ["003_add_audit_log.sql", "audit_log"],
        "value": None,
        "structural": ["created_at", "event", "id"],
    },
    "config_env": {
        "exact": ["SHOPAPI_RATE_LIMIT_RPS", "rate_limit_rps"],
        "value": "42",
        "structural": [],
    },
}


def pick_transcript(benchmark: str) -> list[dict]:
    """Return the S1 messages from the first available frozen Stage 1A run."""
    base = Path(f"results/stage1_{benchmark}")
    for run in sorted(base.glob("*-*")):
        p = run / "session_1_messages.json"
        if p.exists():
            msgs = json.loads(p.read_text())
            if msgs:
                return msgs
    raise RuntimeError(f"no S1 transcript for {benchmark}")


def measure(benchmark: str, messages: list[dict], i: int) -> dict:
    gt = GROUND_TRUTH[benchmark]
    rec = {"benchmark": benchmark, "trial": i, "parse_ok": None,
           "schema_valid": None, "failure": None,
           "exact_hits": {}, "structural_hits": {}, "value_hit": None,
           "serialized_tokens": None}
    try:
        state, raw = extract_c_state(messages)
    except ExtractionError as e:
        rec["parse_ok"] = False
        rec["failure"] = str(e)
        return rec

    rec["parse_ok"] = True
    # schema validity: C-v0.1 with the 9 fixed keys
    need = {"schema_version", "goals", "tasks", "decisions", "entities",
            "facts", "events", "failures", "dependencies", "current_state"}
    rec["schema_valid"] = state.get("schema_version") == "C-v0.1" and need.issubset(state.keys())

    for tok in gt["exact"]:
        rec["exact_hits"][tok] = tok in raw
    for tok in gt["structural"]:
        # structural: presence in the serialized text (which is what S2 sees)
        rec["structural_hits"][tok] = tok in serialize_full(state)
    if gt["value"] is not None:
        import re
        rec["value_hit"] = bool(re.search(rf"\b{gt['value']}\b", raw))

    rec["serialized_tokens"] = count_tokens(serialize_full(state))
    return rec


def main() -> int:
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 5
    out_dir = Path("results") / "extractor_reliability"
    out_dir.mkdir(parents=True, exist_ok=True)

    rows = []
    for bench in BENCHMARKS:
        msgs = pick_transcript(bench)
        print(f"== {bench}: transcript has {len(msgs)} messages ==")
        for i in range(n):
            r = measure(bench, msgs, i)
            rows.append(r)
            print(f"   trial {i}: parse={r['parse_ok']} "
                  f"schema={r['schema_valid']} "
                  f"exact={r['exact_hits']} "
                  f"val={r['value_hit']} "
                  f"tok={r['serialized_tokens']} "
                  f"fail={r['failure']}")

    (out_dir / "reliability.json").write_text(json.dumps(rows, indent=2))

    # Summary
    print("\n=== SUMMARY ===")
    for bench in BENCHMARKS:
        b_rows = [r for r in rows if r["benchmark"] == bench]
        parse = sum(1 for r in b_rows if r["parse_ok"]) / len(b_rows)
        schema = sum(1 for r in b_rows if r["schema_valid"]) / len(b_rows)
        print(f"{bench}: parse={parse:.0%} schema={schema:.0%} "
              f"over {len(b_rows)} trials")
    return 0


if __name__ == "__main__":
    sys.exit(main())