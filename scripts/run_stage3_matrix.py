"""Stage 3 matrix launcher: 3 benchmarks x 4 conditions x 4 budgets x 5 seeds.

Frozen Stage 3 scope: fastapi/schema_migration/config_env x A/B/C/D x
1024/2048/4096/8192 x seeds 1-5. AMD-002 C recovery engaged. Results under
results/stage3_<benchmark>/.
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
OUT = ROOT / "results" / "stage3_matrix.log"

BENCHMARKS = ["fastapi", "schema_migration", "config_env"]
CONDITIONS = ["A", "B", "C", "D"]
BUDGETS = [1024, 2048, 4096, 8192]
SEEDS = [1, 2, 3, 4, 5]


def completed() -> set:
    done = set()
    for bench in BENCHMARKS:
        f = ROOT / "results" / f"stage3_{bench}" / "summary.json"
        if not f.exists():
            continue
        for r in json.loads(f.read_text()).get("runs", []):
            done.add((bench, r["condition"], r["budget"], r["seed"]))
    return done


def main() -> int:
    lock = ROOT / "results" / "stage3_matrix.lock"
    try:
        fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        os.close(fd)
    except FileExistsError:
        print("stage3 matrix lock exists; refusing duplicate launch")
        return 0
    try:
        done = completed()
        todo = queue.Queue()
        for bench in BENCHMARKS:
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
                    cell_log = ROOT / "results" / f"stage3_cell_{bench}_{cond}_{budget}_{seed}.log"
                    log.write(
                        f"\n===== {bench}/{cond}/b{budget}/s{seed} "
                        f"start {time.strftime('%F %T')} =====\n".encode())
                    log.flush()
                    with open(cell_log, "ab") as clog:
                        p = subprocess.run(
                            [str(PY), str(CELL), "--benchmark", bench,
                             "--condition", cond, "--budget", str(budget),
                             "--seed", str(seed),
                             "--out-root", f"results/stage3_{bench}"],
                            cwd=ROOT, stdout=clog, stderr=clog,
                        )
                    log.write(f"{bench}/{cond}/b{budget}/s{seed} "
                              f"exit={p.returncode}\n".encode())
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