"""Phase 4B matrix: 6 benchmarks x 5 conditions x 4 budgets x 5 seeds = 600 cells.

Seed-outermost ordering: partial completion stays a balanced design (all
conditions/budgets covered at completed seeds). 2 workers (operational choice,
AMD-005 lesson). Cells exit 3 (provider failure) are re-queued up to 3 times;
only then written as permanently-excluded infra rows.
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
ORACLE = ROOT / "scripts" / "c_oracle_ablation.py"
OUT = ROOT / "results" / "phase4b_matrix.log"

BENCHES = ["fastapi", "schema_migration", "config_env",
           "cache_policy", "entity_relationship", "evolving_state"]
CONDITIONS = ["A", "B", "C", "D", "O"]   # O = Oracle-C (diagnostic arm)
BUDGETS = [1024, 2048, 4096, 8192]
SEEDS = [1, 2, 3, 4, 5]
MAX_CELL_RETRIES = 3


def completed() -> set:
    done = set()
    for bench in BENCHES:
        for base in (f"phase4_{bench}", f"phase4_oracle/{bench}"):
            f = ROOT / "results" / base / "summary.json"
            if not f.exists():
                continue
            try:
                for r in json.loads(f.read_text()).get("runs", []):
                    done.add((bench, r["condition"], r["budget"], r["seed"]))
            except Exception:
                pass  # corrupted ledger: run dirs win at cell level anyway
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
        # Seed-outermost: partial completion stays balanced.
        for seed in SEEDS:
            for bench in BENCHES:
                for cond in CONDITIONS:
                    for budget in BUDGETS:
                        if (bench, cond, budget, seed) not in done:
                            todo.put((bench, cond, budget, seed))

        workers = int(os.environ.get("STAGE1_WORKERS", "2"))
        retries: dict = {}
        with open(OUT, "ab") as log:
            def run_cell(bench, cond, budget, seed) -> int:
                script = ORACLE if cond == "O" else CELL
                cl = ROOT / "results" / f"p4b_{bench}_{cond}_{budget}_{seed}.log"
                log.write(
                    f"\n===== 4B {bench}/{cond}/b{budget}/s{seed} start "
                    f"{time.strftime('%F %T')} =====\n".encode())
                log.flush()
                with open(cl, "ab") as cf:
                    p = subprocess.run(
                        [str(PY), str(script), "--benchmark", bench,
                         "--budget", str(budget), "--seed", str(seed)]
                        + ([] if cond == "O" else ["--condition", cond])
                        + (["--out-root", f"results/phase4_{bench}"]
                           if cond != "O" else []),
                        cwd=ROOT, stdout=cf, stderr=cf,
                    )
                log.write(f"4B {bench}/{cond}/b{budget}/s{seed} "
                          f"exit={p.returncode}\n".encode())
                log.flush()
                return p.returncode

            def worker():
                while True:
                    try:
                        bench, cond, budget, seed = todo.get_nowait()
                    except queue.Empty:
                        return
                    rc = run_cell(bench, cond, budget, seed)
                    if rc == 3:  # provider failure: requeue, bounded
                        key = (bench, cond, budget, seed)
                        n = retries.get(key, 0) + 1
                        retries[key] = n
                        if n < MAX_CELL_RETRIES:
                            todo.put((bench, cond, budget, seed))
                            log.write(f"  requeued {key} (attempt {n}/{MAX_CELL_RETRIES})\n".encode())
                            log.flush()
                        else:
                            log.write(f"  {key}: permanently infra-failed after {n} attempts\n".encode())
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