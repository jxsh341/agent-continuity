"""Replicate matrix launcher: 4 conditions x 3 seeds @ 2048, sequential.

Each run is a fresh subprocess (hard process boundary), its own
workspace, memory store, and results directory. Runs append into
results/stage0_4/summary.json via run_stage0_4_fastapi.py.
"""

from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).parent.parent
PY = ROOT / ".venv" / "Scripts" / "python.exe"
SCRIPT = ROOT / "scripts" / "run_stage0_4_fastapi.py"
OUT = ROOT / "results" / "replicates_matrix.log"

CONDITIONS = ["A", "B", "C", "D"]
SEEDS = [1, 2, 3]
BUDGET = 2048


def completed() -> set:
    """Condition/seed combos with an entry already in summary.json.
    Resumability rule: a run is complete iff it finished and wrote
    itself into the ledger. Everything else is redone."""
    summary = ROOT / "results" / "stage0_4" / "summary.json"
    if not summary.exists():
        return set()
    data = json.loads(summary.read_text())
    return {
        (r["condition"], r.get("seed", 1), r.get("budget", 2048))
        for r in data.get("runs", [])
        if r.get("seed") is not None  # replicate rows only; Stage-0 singles rerun
    }


def main() -> int:
    done = completed()
    with open(OUT, "ab") as log:
        for cond in CONDITIONS:
            for seed in SEEDS:
                if (cond, seed, BUDGET) in done:
                    continue
                msg = f"\n===== {cond} seed={seed} budget={BUDGET} start {time.strftime('%H:%M:%S')} =====\n"
                log.write(msg.encode())
                log.flush()
                p = subprocess.run(
                    [str(PY), str(SCRIPT), "--condition", cond,
                     "--budget", str(BUDGET), "--seed", str(seed)],
                    cwd=ROOT, stdout=log, stderr=log,
                )
                log.write(f"exit={p.returncode}\n".encode())
                log.flush()
                done.add((cond, seed, BUDGET))
    return 0


if __name__ == "__main__":
    sys.exit(main())
