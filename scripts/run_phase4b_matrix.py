"""Phase 4B launcher: budget-curve batch.

6 benchmarks x A/B/C/D x budgets {1024, 4096} x seeds {1..5} = 240 cells.
Completes the 1K->2K->4K->8K response curve (2K/8K already covered by the
pilot + Stage 3). Results under results/phase4b_<benchmark>/.
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
OUT = ROOT / "results" / "phase4b_matrix.log"

BENCHES = ["fastapi", "schema_migration", "config_env",
           "cache_policy", "entity_relationship", "evolving_state"]
CONDITIONS = ["A", "B", "C", "D"]
BUDGETS = [1024, 4096]
SEEDS = [1, 2, 3, 4, 5]


def completed() -> set:
    done = set()
    for bench in BENCHES:
        f = ROOT / "results" / f"phase4b_{bench}" / "summary.json"
        if not f.exists():
            continue
        for r in json.loads(f.read_text()).get("runs", []):
            done.add((bench, r["condition"], r["budget"], r["seed"]))
    return done


def main() -> int:
    lock = ROOT / "results" / "phase4b_matrix.lock"
    try:
        fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        os.close(fd)
    except FileExistsError:
        print("phase4b lock exists; refusing duplicate launch")
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

        workers = int(os.environ.get("STAGE1_WORKERS", "2"))
        with open(OUT, "ab") as log:
            def worker():
                while True:
                    try:
                        bench, cond, budget, seed = todo.get_nowait()
                    except queue.Empty:
                        return
                    cl = ROOT / "results" / f"p4b_cell_{bench}_{cond}_{budget}_{seed}.log"
                    log.write(
                        f"\n===== 4B {bench}/{cond}/b{budget}/s{seed} start "
                        f"{time.strftime('%F %T')} =====\n".encode())
                    log.flush()
                    with open(cl, "ab") as cf:
                        p = subprocess.run(
                            [str(PY), str(CELL), "--benchmark", bench,
                             "--condition", cond, "--budget", str(budget),
                             "--seed", str(seed),
                             "--out-root", "results/phase4b_" + bench],
                            cwd=ROOT, stdout=cf, stderr=cf,
                        )
                    log.write(f"{bench}/{cond}/b{budget}/s{seed} "
                              f"exit={p.returncode}\n".encode())
                    log.flush()
                    todo.task_done()

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