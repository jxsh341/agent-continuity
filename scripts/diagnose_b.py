"""Offline B diagnosis: run B.prepare() against an existing S1
transcript with NO coding agent. Measures extraction latency, Mem0
calls, memories created, memory contents, search latency, token counts,
and failure/timeout behavior.

Usage:
    python scripts/diagnose_b.py [run_dir]
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from conditions.b import ConditionB  # noqa: E402
from scripts.run_c_from_transcript import messages_from_events  # noqa: E402

from continuity.tokens import count_tokens  # noqa: E402


def main() -> int:
    run_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(
        "results/stage0_4/C-1-d2e3b391"
    )
    events = json.loads((run_dir / "session_1_events.json").read_text())
    messages = messages_from_events(events)
    print(f"loaded {len(messages)} messages from {run_dir}")

    out_dir = Path("results") / "b_diagnosis"
    out_dir.mkdir(exist_ok=True)

    report: dict = {"n_messages": len(messages)}

    b = ConditionB(out_dir / "store")
    t0 = time.perf_counter()
    try:
        b.prepare({"session_index": 1, "messages": messages})
        report["prepare"] = {"ok": True, "seconds": round(time.perf_counter() - t0, 1)}
    except Exception as e:
        report["prepare"] = {
            "ok": False, "seconds": round(time.perf_counter() - t0, 1),
            "error": f"{type(e).__name__}: {e}",
        }

    # retrieval probes
    for label, query in [
        ("task-echo", "Implement the reports endpoint exactly as designed in the earlier session"),
        ("generic", "project state, decisions, and open work"),
    ]:
        t0 = time.perf_counter()
        try:
            artifact = b.build_context(2048, task=query)
            report[f"search:{label}"] = {
                "ok": True, "seconds": round(time.perf_counter() - t0, 1),
                "tokens": artifact.token_count,
                "provenance": artifact.provenance,
                "text": artifact.text[:1200],
            }
        except Exception as e:
            report[f"search:{label}"] = {
                "ok": False, "seconds": round(time.perf_counter() - t0, 1),
                "error": f"{type(e).__name__}: {e}",
            }

    meta = b.metadata()
    report["sessions"] = meta["sessions_consumed"]
    (out_dir / "diagnosis.json").write_text(json.dumps(report, indent=2))
    print(json.dumps({k: v for k, v in report.items() if k != "search:generic"}, indent=2)[:2500])
    return 0


if __name__ == "__main__":
    sys.exit(main())
