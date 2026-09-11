"""Long-transcript extractor stratification (diagnostic, frozen components).

Uses the ACTUAL frozen Stage 1A S1 transcripts (one extraction each; the
extractor is T=0 so repeated trials are not manufactured). Stratifies by
message count and by token count. Separates parse failure from schema
failure from field omission/paraphrase from success, and keeps the
config_env key/value omission as its own phenomenon.

Outputs:
  results/extractor_stratification/manifest.json
  results/extractor_stratification/trials.jsonl
  results/extractor_stratification/summary.json
  results/extractor_stratification/analysis.md
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from benchmark.registry import BENCHMARKS  # noqa: E402
from continuity.tokens import count_tokens  # noqa: E402
from extractors.c_extractor import ExtractionError, extract_c_state  # noqa: E402
from extractors.c_extractor import serialize_transcript  # noqa: E402
from serialization.c_serializer import serialize_full  # noqa: E402

# Ground truth per benchmark, classified by fidelity type.
GT = {
    "fastapi": {
        "exact": ["/reports/summary", "page_size", "reports"],
        "value": "7",
        "structural": ["category", "count"],
        "conceptual": ["aggregat", "categor"],
    },
    "schema_migration": {
        "exact": ["003_add_audit_log.sql", "audit_log"],
        "value": None,
        "structural": ["created_at", "event", "id"],
        "conceptual": ["migration"],
    },
    "config_env": {
        "exact": ["SHOPAPI_RATE_LIMIT_RPS", "rate_limit_rps"],
        "value": "42",
        "structural": [],
        "conceptual": ["override", "UPPER_SNAKE"],
    },
}


def bin_label(n: int, lo: int, hi: int) -> str | None:
    return None if not (lo <= n <= hi) else f"{lo}-{hi}"


def message_bin(n: int) -> str:
    for lo, hi in [(0, 20), (21, 40), (41, 60), (61, 1000)]:
        if lo <= n <= hi:
            return f"{lo}-{hi} msgs"
    return "other"


def token_bin(n: int) -> str:
    for lo, hi in [(0, 1500), (1501, 3000), (3001, 5000), (5001, 100000)]:
        if lo <= n <= hi:
            return f"{lo}-{hi} tok"
    return "other"


def fidelity(gt: dict, raw: str, serialized: str) -> dict:
    import re
    exact = {t: (t in raw) for t in gt["exact"]}
    structural = {t: (t in serialized) for t in gt["structural"]}
    value = None
    if gt["value"] is not None:
        value = bool(re.search(rf"\b{gt['value']}\b", raw))
    conceptual = {t: (t.lower() in raw.lower()) for t in gt["conceptual"]}
    return {
        "exact_identifiers": exact,
        "exact_value": value,
        "structural": structural,
        "conceptual": conceptual,
    }


def main() -> int:
    out_dir = Path("results") / "extractor_stratification"
    out_dir.mkdir(parents=True, exist_ok=True)
    raw_dir = out_dir / "raw"
    raw_dir.mkdir(exist_ok=True)

    trials = []
    manifest = []
    fs = {}

    for bench in BENCHMARKS:
        summary = json.loads(
            (Path("results") / f"stage1_{bench}" / "summary.json").read_text()
        )["runs"]
        success = {r["run_id"]: r["success"] for r in summary}
        for run in sorted((Path("results") / f"stage1_{bench}").glob("*-*")):
            mp = run / "session_1_messages.json"
            if not mp.exists():
                continue
            msgs = json.loads(mp.read_text())
            transcript = serialize_transcript(msgs)
            n_msg = len(msgs)
            n_tok = count_tokens(transcript)
            run_id = run.name
            gt = GT[bench]

            entry = {
                "benchmark": bench,
                "run_id": run_id,
                "stage1a_success": success.get(run_id),
                "n_messages": n_msg,
                "n_tokens": n_tok,
                "msg_bin": message_bin(n_msg),
                "tok_bin": token_bin(n_tok),
            }

            t0 = time.perf_counter()
            try:
                state, raw = extract_c_state(msgs)
                entry["parse_success"] = True
                entry["failure_category"] = None
                need = {"schema_version", "goals", "tasks", "decisions",
                        "entities", "facts", "events", "failures",
                        "dependencies", "current_state"}
                entry["schema_valid"] = (
                    state.get("schema_version") == "C-v0.1"
                    and need.issubset(state.keys())
                )
                ser = serialize_full(state)
                entry["extracted_tokens"] = count_tokens(ser)
                entry["fidelity"] = fidelity(gt, raw, ser)
                (raw_dir / f"{bench}_{run_id}.txt").write_text(raw)
                entry["raw_path"] = f"raw/{bench}_{run_id}.txt"
            except ExtractionError as e:
                entry["parse_success"] = False
                entry["schema_valid"] = False
                entry["extracted_tokens"] = None
                entry["fidelity"] = None
                entry["failure_category"] = "parse" if "JSON" in str(e) else str(e)

            entry["latency_s"] = round(time.perf_counter() - t0, 2)
            trials.append(entry)
            manifest.append({
                "benchmark": bench, "run_id": run_id,
                "n_messages": n_msg, "n_tokens": n_tok,
                "parse_success": entry["parse_success"],
                "failure_category": entry["failure_category"],
            })
            print(f"{bench:16} {run_id} msgs={n_msg:3} tok={n_tok:5} "
                  f"parse={entry['parse_success']} "
                  f"cat={entry['failure_category']}", flush=True)

    (out_dir / "trials.jsonl").write_text(
        "\n".join(json.dumps(t) for t in trials)
    )
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2))
    (out_dir / "summary.json").write_text(json.dumps(trials, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())