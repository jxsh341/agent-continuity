"""Stage 1A executor: 3 benchmarks x 4 conditions x 2 budgets x 5 seeds.

One child process per cell; per-benchmark ledgers; resumable; single
instance enforced by lockfile.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).parent.parent
PY = ROOT / ".venv" / "Scripts" / "python.exe"
CELL = ROOT / "scripts" / "run_stage1_cell.py"
OUT = ROOT / "results" / "stage1_matrix.log"

BENCHMARKS = ["fastapi", "schema_migration", "config_env"]
CONDITIONS = ["A", "B", "C", "D"]
BUDGETS = [2048, 8192]
SEEDS = [1, 2, 3, 4, 5]


def completed() -> set:
    done = set()
    for bench in BENCHMARKS:
        f = ROOT / "results" / f"stage1_{bench}" / "summary.json"
        if not f.exists():
            continue
        data = json.loads(f.read_text())
        for r in data.get("runs", []):
            done.add((bench, r["condition"], r.get("budget", 2048),
                      r.get("seed", 1)))
    return done


def main() -> int:
    lock = ROOT / "results" / "stage1_matrix.lock"
    try:
        fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        os.close(fd)
    except FileExistsError:
        print("stage1 matrix lock exists; refusing duplicate launch")
        return 0

    # Parallelism is purely infrastructural: cells are mutually orthogonal
    # (own workspace, run dir, memory store). Identical inputs whether
    # serial or parallel. Config/concurrency is recorded in runner metadata.
    workers = int(os.environ.get("STAGE1_WORKERS", "4"))
    try:
        import queue
        import threading

        todo = queue.Queue()
        done = completed()
        for bench in BENCHMARKS:
            for cond in CONDITIONS:
                for budget in BUDGETS:
                    for seed in SEEDS:
                        if (bench, cond, budget, seed) not in done:
                            todo.put((bench, cond, budget, seed))

        with open(OUT, "ab") as log:
            def worker() -> None:
                while True:
                    try:
                        bench, cond, budget, seed = todo.get_nowait()
                    except queue.Empty:
                        return
                    log.write(
                        f"\n===== {bench}/{cond}/b{budget}/s{seed} "
                        f"start {time.strftime('%F %T')} =====\n".encode()
                    )
                    log.flush()
                    # One log per cell avoids interleaved stdout
                    cell_log = (
                        ROOT / "results" /
                        f"cell_{bench}_{cond}_{budget}_{seed}.log"
                    )
                    with open(cell_log, "ab") as clog:
                        p = subprocess.run(
                            [str(PY), str(CELL), "--benchmark", bench,
                             "--condition", cond, "--budget", str(budget),
                             "--seed", str(seed)],
                            cwd=ROOT, stdout=clog, stderr=clog,
                        )
                    log.write(
                        f"cell {bench}/{cond}/b{budget}/s{seed} "
                        f"exit={p.returncode}\n".encode()
                    )
                    log.flush()
                    todo.task_done()

            threads = [
                threading.Thread(target=worker, daemon=True)
                for _ in range(workers)
            ]
            for t in threads:
                t.start()
            todo.join()
    finally:
        lock.unlink(missing_ok=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
