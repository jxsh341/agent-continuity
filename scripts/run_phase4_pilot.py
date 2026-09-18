"""Phase 4 pilot: machinery/integrity test, not evidence.

Scope: fastapi / entity_relationship / evolving_state
         × A/B/C/D × budgets {2048, 8192} × seeds {1,2,3} = 72 cells.

Records cell status into results/phase4_pilot/<benchmark>/... summary + run dirs.
"""

from __future__ import annotations

import json
import os
import queue
import subprocess
import sys
import threading
import time
from pathlib import Path

ROOT = Path(__file__).parent.parent
PY = ROOT / ".venv" / "Scripts" / "python.exe"
CELL = ROOT / "scripts" / "run_stage1_cell.py"
OUT = ROOT / "results" / "phase4_pilot_matrix.log"

BENCHES = ["fastapi", "entity_relationship", "evolving_state"]
CONDITIONS = ["A", "B", "C", "D"]
BUDGETS = [2048, 8192]
SEEDS = [1, 2, 3]


def completed() -> set:
    done = set()
    for bench in BENCHES:
        f = ROOT / "results" / f"phase4_{bench}" / "summary.json"
        if not f.exists():
            continue
        for r in json.loads(f.read_text()).get("runs", []):
            done.add((bench, r["condition"], r["budget"], r["seed"]))
    return done


def main() -> int:
    lock = ROOT / "results" / "phase4_matrix.lock"
    try:
        fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        os.close(fd)
    except FileExistsError:
        print("phase4 matrix lock exists; refusing duplicate launch")
        return 0
    try:
        done = completed()
        todo = queue.Queue()
        for bench in BENCHES:
            for cond in CONDITIONS:
                for budget in BUDGETS:
                    for seed in SEEDS:
                        if (bench, cond, budget, seed) not in done:
                            todo.put((bench, cond, budget, seed))

        workers = int(os.environ.get("STAGE1_WORKERS", "4"))
        with open(OUT, "ab") as log:
            def worker():
                while True:
                    try:
                        bench, cond, budget, seed = todo.get_nowait()
                    except queue.Empty:
                        return
                    log.write(
                        f"\n===== pilot {bench}/{cond}/b{budget}/s{seed} start "
                        f"{time.strftime('%F %T')} =====\n".encode())
                    log.flush()
                    cl = ROOT / "results" / f"p4_cell_{bench}_{cond}_{budget}_{seed}.log"
                    with open(cl, "ab") as cf:
                        p = subprocess.run(
                            [str(PY), str(CELL), "--benchmark", bench,
                             "--condition", cond, "--budget", str(budget),
                             "--seed", str(seed),
                             "--out-root", "results/phase4_" + bench],
                            cwd=ROOT, stdout=cf, stderr=cf,
                        )
                    log.write(f"{bench}/{cond}/b{budget}/s{seed} exit={p.returncode}\n"
                              .encode())
                    log.flush()

            threads = [threading.Thread(target=worker, daemon=True)
                       for _ in range(workers)]
            for t in threads:
                t.start()
            todo.join()
    finally:
        lock.unlink(missing_ok=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())