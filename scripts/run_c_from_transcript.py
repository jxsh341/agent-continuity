"""Milestone 0.3-C step 7: run the C extractor against an EXISTING S1
transcript (no new agent session). Engineering validation only.

Usage:
    python scripts/run_c_from_transcript.py <run_dir>
Defaults to the A-condition Stage 0.4 run (real FastAPI S1).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from conditions.c import ConditionC  # noqa: E402


def messages_from_events(events: list[dict]) -> list[dict]:
    out = []
    for e in events:
        msg = e.get("llm_message")
        if not isinstance(msg, dict):
            continue
        parts = msg.get("content") or []
        text = "".join(p.get("text", "") for p in parts if isinstance(p, dict))
        if text:
            out.append({"role": msg.get("role", "?"), "content": text})
    return out


def main() -> int:
    run_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(
        "results/stage0_4/A-1-500dd77e"
    )
    events = json.loads((run_dir / "session_1_events.json").read_text())
    messages = messages_from_events(events)
    print(f"loaded {len(messages)} messages from {run_dir}")

    out_dir = Path("results") / "c_from_transcript"
    out_dir.mkdir(exist_ok=True)
    c = ConditionC(out_dir)
    c.prepare({"session_index": 1, "messages": messages})
    artifact = c.build_context(2048)

    print("\n=== C context (2048) ===\n")
    print(artifact.text)
    print("\n=== meta ===")
    print(json.dumps(c.metadata(), indent=2)[:800])
    return 0


if __name__ == "__main__":
    sys.exit(main())
