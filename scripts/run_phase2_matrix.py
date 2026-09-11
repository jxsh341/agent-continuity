"""Phase 2 matrix launcher: 3 benchmarks x 2 budgets x 3 seeds = 18 S2 cells.

Resumable (skips cells whose result file already exists), 4 workers, lockfile.
"""

from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).parent.parent
PY = ROOT / ".venv" / "Scripts" / "python.exe"
CELL = ROOT / "scripts" / "run_phase2_cell.py"
OUT = ROOT / "results" / "phase2_matrix.log"

BENCHMARKS = ["fastapi", "schema_migration", "config_env"]
BUDGETS = [2048, 8192]
SEEDS = [1, 2, 3]


def completed() -> set:
    done = set()
    for bench in BENCHMARKS:
        d = ROOT / "results" / "phase2" / bench
        if not d.exists():
            continue
        for f in d.glob("cell_*.json"):
            name = f.name  # cell_<seed>_<budget>.json
            parts = name[len("cell_"):-len(".json")].split("_")
            seed, budget = int(parts[0]), int(parts[1])
            done.add((bench, budget, seed))
    return done


def main() -> int:
    lock = ROOT / "results" / "phase2_matrix.lock"
    try:
        fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        os.close(fd)
    except FileExistsError:
        print("phase2 lock exists; refusing duplicate launch")
        return 0
    try:
        import queue
        import threading

        done = completed()
        todo = queue.Queue()
        for bench in BENCHMARKS:
            for budget in BUDGETS:
                for seed in SEEDS:
                    if (bench, budget, seed) not in done:
                        todo.put((bench, budget, seed))

        workers = int(os.environ.get("STAGE1_WORKERS", "4"))
        with open(OUT, "ab") as log:
            def worker():
                while True:
                    try:
                        bench, budget, seed = todo.get_nowait()
                    except queue.Empty:
                        return
                    log.write(f"\n===== {bench}/b{budget}/s{seed} start "
                              f"{time.strftime('%F %T')} =====\n".encode())
                    log.flush()
                    p = subprocess.run(
                        [str(PY), str(CELL), "--benchmark", bench,
                         "--budget", str(budget), "--seed", str(seed)],
                        cwd=ROOT,
                        stdout=log, stderr=log,
                    )
                    log.write(f"{bench}/b{budget}/s{seed} exit={p.returncode}\n"
                              .encode())
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