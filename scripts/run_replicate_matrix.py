"""Replicate matrix launcher: 4 conditions x 3 seeds @ 2048, sequential.

Each run is a fresh subprocess (hard process boundary), its own
workspace, memory store, and results directory. Runs append into
results/stage0_4/summary.json via run_stage0_4_fastapi.py.
"""

from __future__ import annotations

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


def main() -> int:
    with open(OUT, "ab") as log:
        for cond in CONDITIONS:
            for seed in SEEDS:
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
    return 0


if __name__ == "__main__":
    sys.exit(main())
