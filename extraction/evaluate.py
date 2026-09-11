"""Extraction evaluation driver (Phase 1).

Replays the saved frozen extractor outputs from the stratification study
(results/extractor_stratification/{raw/,trials.jsonl}) and scores each against
the gold standard. CLI can also RE-RUN the extractor over the frozen transcripts
(--extract) but the default uses the saved outputs so results are reproducible
without new LLM calls.

Outputs:
  results/extraction_eval/per_benchmark.json
  results/extraction_eval/per_transcript.json
  results/extraction_eval/summary.json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from benchmark.registry import BENCHMARKS  # noqa: E402
from extraction.gold import CATEGORIES, GOLD  # noqa: E402
from extraction.metrics import aggregate, evaluate_extraction  # noqa: E402
from serialization.c_serializer import serialize_full  # noqa: E402


def load_saved():
    trials_path = Path("results/extractor_stratification/trials.jsonl")
    raw_dir = Path("results/extractor_stratification/raw")
    rows = [json.loads(l) for l in trials_path.read_text().splitlines()]
    return rows, raw_dir


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--extract", action="store_true",
                    help="re-run LUThao extractor instead of using saved outputs")
    a = ap.parse_args()

    out_dir = Path("results/extraction_eval")
    out_dir.mkdir(parents=True, exist_ok=True)

    per_transcript = []

    if a.extract:
        from extractors.c_extractor import ExtractionError, extract_c_state
        rows = []
        raw_dir = Path("results/extractor_stratification/raw")
        raw_dir.mkdir(parents=True, exist_ok=True)
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
                rows.append({
                    "benchmark": bench, "run_id": run.name,
                    "stage1a_success": success.get(run.name), "messages": msgs,
                })
        for r in rows:
            try:
                state, raw = extract_c_state(r["messages"])
                parse_ok, schema_ok = True, state.get("schema_version") == "C-v0.1"
                ser = serialize_full(state)
            except Exception:  # noqa: BLE001
                parse_ok, schema_ok, ser, raw = False, False, "", ""
            (raw_dir / f"{r['benchmark']}_{r['run_id']}.txt").write_text(raw)
            per_transcript.append(_score(r, raw, ser, parse_ok, schema_ok))
    else:
        rows, raw_dir = load_saved()
        from extractors.c_extractor import normalize_state, parse_output
        for r in rows:
            rp = raw_dir / f"{r['benchmark']}_{r['run_id']}.txt"
            raw = rp.read_text(encoding="utf-8", errors="ignore") if rp.exists() else ""
            ser = ""
            if r.get("parse_success"):
                try:
                    ser = serialize_full(normalize_state(parse_output(raw)))
                except Exception:  # noqa: BLE001
                    ser = ""
            per_transcript.append(_score(r, raw, ser, r.get("parse_success", False),
                                         r.get("schema_valid", False)))

    (out_dir / "per_transcript.json").write_text(
        json.dumps(per_transcript, indent=2)
    )

    summary = {}
    for bench in BENCHMARKS:
        summary[bench] = aggregate(per_transcript, bench)
    summary["overall"] = aggregate(per_transcript)
    (out_dir / "summary.json").write_text(json.dumps(summary, indent=2))

    # Compact print
    print("=== extraction evaluation (recall among parse-success) ===")
    order = ["overall"] + list(BENCHMARKS)
    for k in order:
        if k not in summary:
            continue
        s = summary[k]
        if s.get("n", 0) == 0:
            continue
        print(f"{k:18} n={s['n']} parse={s['parse_rate']:.0%} "
              f"ident={s['exact_identifier_recall']:.0%} "
              f"val={_fmt(s['exact_value_recall'])} "
              f"struct={_fmt(s['structural_recall'])} "
              f"neg={_fmt(s['negative_instruction_recall'])} "
              f"scope={_fmt(s['temporal_scope_recall'])} "
              f"overall={s['overall_recall']:.0%}")
    return 0


def _fmt(v):
    return "n/a" if v is None else f"{v:.0%}"


def _score(r: dict, raw: str, ser: str, parse_ok: bool, schema_ok: bool) -> dict:
    e = evaluate_extraction(r["benchmark"], raw, ser, parse_ok, schema_ok)
    e["run_id"] = r.get("run_id")
    e["stage1a_success"] = r.get("stage1a_success")
    return e


if __name__ == "__main__":
    sys.exit(main())