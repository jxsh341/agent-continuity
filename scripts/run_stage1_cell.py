"""Stage 1.0 runner: one (benchmark, condition, budget, seed) cell.

Generic version of the Stage 0.4 runner: benchmark selected by name from
benchmark.registry. Offline-capable (validation mode) though normally runs
the real session.

Usage:
    .venv\\Scripts\\python scripts\\run_stage1_cell.py \\
        --benchmark schema_migration --condition C --budget 2048 --seed 1
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from agent import ModelConfig, OpenHandsCodingAgent  # noqa: E402
from benchmark.registry import BENCHMARKS  # noqa: E402
from continuity.models import RunConfig  # noqa: E402
from continuity.runner import ExperimentRunner  # noqa: E402

ROOT = Path(__file__).parent.parent


def pytest_run(workspace: Path, *args: str) -> dict:
    p = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", "--tb=no", *args],
        cwd=workspace, capture_output=True, text=True,
    )
    return {"passed": p.returncode == 0, "tail": p.stdout[-1500:]}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--benchmark", required=True, choices=list(BENCHMARKS))
    ap.add_argument("--condition", required=True, choices=list("ABCD"))
    ap.add_argument("--budget", type=int, required=True)
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--out-root", type=str, default=None,
                    help="override results root (Stage 3 writes elsewhere)")
    a = ap.parse_args()

    bench = BENCHMARKS[a.benchmark]

    gs = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT,
                        capture_output=True, text=True)
    sd = subprocess.run(["git", "status", "--short"], cwd=ROOT,
                        capture_output=True, text=True)
    if sd.stdout.strip():
        raise RuntimeError("tracked tree dirty; refuse to run canonical cell")
    experiment_commit = gs.stdout.strip()

    out_root = (
        (ROOT / a.out_root if not Path(a.out_root).is_absolute() else Path(a.out_root))
        if a.out_root else ROOT / "results" / f"stage1_{a.benchmark}"
    )
    out_root.mkdir(parents=True, exist_ok=True)

    g = json.loads((ROOT / "configs" / "framework_pin.json").read_text())
    config = ModelConfig.from_env()
    agent = OpenHandsCodingAgent(config, framework_commit=g["commit"])

    seed = Path(tempfile.mkdtemp(prefix=f"s1_{a.benchmark}_seed_"))
    bench.make_seed(seed)
    workspace = Path(
        tempfile.mkdtemp(prefix=f"s1_{a.benchmark}_{a.condition}_{a.budget}_")
    )
    shutil.copytree(seed, workspace, dirs_exist_ok=True)

    leaked: dict = {}

    def after(idx: int, ws: Path) -> None:
        removed = []
        for name in ("AGENTS.md", ".agents.md"):
            p = ws / name
            if p.exists():
                p.unlink()
                removed.append(name)
        leaked.setdefault("notes_scrubbed", []).append(
            {"after_session": idx, "removed": removed}
        )
        if idx == 1:
            leaked["decision_leaked_to_repo"] = bench.contamination_scan(ws)

    def evaluator(ws: Path, idx: int) -> dict:
        if idx == 1:
            r = pytest_run(ws, "tests/")
            r["evaluator"] = "pytest:visible"
            return r
        bench.inject_hidden_tests(ws)
        r = pytest_run(ws, "tests/")
        r["evaluator"] = "pytest:visible+hidden"
        return r

    runner = ExperimentRunner(agent, out_root, framework_pin=g)
    hint = (
        f"The workspace root is: {workspace}\n"
        "Use it verbatim (absolute Windows path) as the tool path prefix.\n\n"
    )
    summary = runner.run(
        RunConfig(condition=a.condition, context_budget=a.budget, run_seed=a.seed),
        tasks=[hint + bench.TASK_S1, hint + bench.TASK_S2],
        workspace=workspace,
        evaluator=evaluator,
        on_session_end=after,
    )

    run_dir = out_root / summary["run_id"]
    s1d = json.loads((run_dir / "session_1.json").read_text())
    s2 = json.loads((run_dir / "session_2.json").read_text())

    # AMD-005: fail closed on provider errors. A provider failure is NOT a
    # condition outcome: the cell gets no ledger row (excluded from every
    # scientific denominator) and the launcher re-queues it.
    provider_err = classify_provider_error(
        s2["agent_error"] or s1d.get("agent_error")
    )
    if provider_err:
        _log_infra(out_root, {
            "run_id": summary["run_id"],
            "benchmark": a.benchmark,
            "condition": a.condition,
            "budget": a.budget,
            "seed": a.seed,
            "classification": provider_err,
            "detail": (s2["agent_error"] or s1d.get("agent_error"))[:300],
        })
        shutil.rmtree(seed, ignore_errors=True)
        shutil.rmtree(workspace, ignore_errors=True)
        return 3

    # Fact-fidelity table for forensic analysis
    ctx_text = s2["context_artifact"]["text"]
    fact_report = {f["id"]: bool(f["check"](ctx_text)) for f in bench.CRITICAL_FACTS}

    entry = {
        "run_id": summary["run_id"],
        "benchmark": a.benchmark,
        "condition": a.condition,
        "budget": a.budget,
        "seed": a.seed,
        "experiment_commit": experiment_commit,
        "s1_visible_tests_passed": s1d["evaluation"]["passed"],
        "s2_all_tests_passed": s2["evaluation"]["passed"],
        "decision_leaked_to_repo": leaked.get("decision_leaked_to_repo", False),
        "fact_fidelity": fact_report,
        "s2_context_tokens": s2["context_artifact"]["token_count"],
        "s2_context_truncated": s2["context_artifact"]["truncated"],
        "s2_agent_error": s2["agent_error"],
        "success": bool(
            summary["all_evaluations_passed"] and not s2["agent_error"]
        ),
    }
    summary_file = out_root / "summary.json"
    _upsert_summary(summary_file, entry)
    print(json.dumps(entry, indent=2, default=str), flush=True)

    shutil.rmtree(seed, ignore_errors=True)
    shutil.rmtree(workspace, ignore_errors=True)
    return 0 if entry["success"] else 1


def classify_provider_error(err: str | None) -> str | None:
    """AMD-005: provider-side failures are infrastructure, not condition
    outcomes. 404 (endpoint/model routing), timeouts, auth, overload, and
    rate limits all mean the cell was not scientifically evaluable."""
    if not err:
        return None
    s = str(err)
    if "NotFoundError" in s or "404" in s:
        return "INFRA_FAILURE_PROVIDER"
    if "timeout" in s.lower() or "Timeout" in s:
        return "INFRA_FAILURE_PROVIDER"
    if "401" in s or "authentication" in s.lower() or "credentials" in s.lower():
        return "INFRA_FAILURE_PROVIDER"
    if "503" in s or "overload" in s.lower() or "Service Unavailable" in s:
        return "INFRA_FAILURE_PROVIDER"
    if "429" in s or "RateLimit" in s:
        return "INFRA_FAILURE_PROVIDER"
    return None


def _log_infra(out_root: Path, record: dict) -> None:
    """Append to the infra ledger (accounting only; excluded from science)."""
    infra_file = out_root / "infra.jsonl"
    with open(infra_file, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, default=str) + "\n")
    print(json.dumps(record, indent=2, default=str), flush=True)


def _upsert_summary(summary_file: Path, entry: dict) -> None:
    """Atomically upsert a cell entry keyed by (condition,budget,seed)."""
    import os as _os
    import time as _time

    deadline = _time.time() + 60
    delay = 0.25
    tmpfile = summary_file.with_suffix(f".tmp.{_os.getpid()}")
    while True:
        try:
            existing = {}
            if summary_file.exists():
                txt = summary_file.read_text(encoding="utf-8")
                existing = json.loads(txt) if txt.strip() else {"runs": []}
            runs = existing.get("runs") or []
            runs = [
                r for r in runs
                if not (
                    r.get("condition") == entry["condition"]
                    and r.get("budget") == entry["budget"]
                    and r.get("seed") == entry["seed"]
                )
            ]
            runs.append(entry)
            existing["runs"] = runs
            with open(tmpfile, "w", encoding="utf-8") as tf:
                json.dump(existing, tf, indent=2)
            _os.replace(tmpfile, summary_file)
            return
        except (OSError, PermissionError):
            if _time.time() > deadline:
                raise
            _time.sleep(delay)
            delay = min(delay * 2, 2.0)


if __name__ == "__main__":
    sys.exit(main())
