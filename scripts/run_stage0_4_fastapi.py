"""Stage 0.4: FastAPI benchmark through the conditions, for real.

Per (condition, budget) run:
    S1: implement DELETE /items/{id}; receive design decisions for a
        future endpoint (conversation-only; must not enter the repo).
    S2: implement the designed endpoint. Hidden tests (injected by the
        evaluator after the agent finishes) assert the S1-only
        decision (page size 7).

Deterministic signals recorded per run:
    s1_tests_passed, s2_all_tests_passed (incl. hidden),
    decision_leaked_to_repo (contamination scan after S1),
    context artifact stats, token metrics.

Usage (resumable; results merge into results/stage0_4/summary.json):
    .venv\\Scripts\\python scripts\\run_stage0_4_fastapi.py --condition A --budget 2048
    .venv\\Scripts\\python scripts\\run_stage0_4_fastapi.py --condition B --budget 2048
    ...
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
from benchmark.fastapi_repo import (  # noqa: E402
    make_seed, inject_hidden_tests, contamination_scan, scrub_session_notes,
    TASK_S1, TASK_S2,
)
from continuity.models import RunConfig  # noqa: E402
from continuity.runner import ExperimentRunner  # noqa: E402

ROOT = Path(__file__).parent.parent
RESULTS = ROOT / "results" / "stage0_4"
SUMMARY = RESULTS / "summary.json"


def pytest_run(workspace: Path, *args: str) -> dict:
    p = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", "--tb=no", *args],
        cwd=workspace, capture_output=True, text=True,
    )
    return {"passed": p.returncode == 0, "tail": p.stdout[-1500:]}


def make_evaluator():
    def _eval(workspace: Path, session_index: int) -> dict:
        if session_index == 1:
            r = pytest_run(workspace, "tests/test_items.py")
            r["evaluator"] = "pytest:visible"
            return r
        inject_hidden_tests(workspace)
        r = pytest_run(workspace, "tests/")
        r["evaluator"] = "pytest:visible+hidden"
        return r
    return _eval


def git_state() -> dict:
    r = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT,
                       capture_output=True, text=True)
    s = subprocess.run(["git", "status", "--short"], cwd=ROOT,
                       capture_output=True, text=True)
    return {"commit": r.stdout.strip(), "dirty": bool(s.stdout.strip())}


def run_one(condition: str, budget: int, seed_run: int) -> dict:
    config = ModelConfig.from_env()
    pin = json.loads((ROOT / "configs" / "framework_pin.json").read_text())
    agent = OpenHandsCodingAgent(config, framework_commit=pin["commit"])
    runner = ExperimentRunner(agent, RESULTS, framework_pin=pin)

    g = git_state()
    if g["dirty"]:
        # results/ is gitignored, so dirtiness here means tracked source
        # changed since the pinned baseline. Fail loudly, not silently.
        raise RuntimeError(
            f"Repository dirty before {condition}/{budget}/seed{seed_run}: "
            "canonical runs require a clean tracked tree."
        )

    seed = Path(tempfile.mkdtemp(prefix="s04_seed_"))
    make_seed(seed)
    workspace = Path(tempfile.mkdtemp(prefix=f"s04_{condition}_{budget}_"))
    shutil.copytree(seed, workspace, dirs_exist_ok=True)

    leaked = {}

    def after_s1(idx: int, ws: Path) -> None:
        # At every session boundary: scrub memory-note surfaces, then
        # check whether the decision leaked into the remaining repo.
        removed = scrub_session_notes(ws)
        leaked.setdefault("notes_scrubbed", []).append(
            {"after_session": idx, "removed": removed}
        )
        if idx == 1:
            leaked["decision_leaked_to_repo"] = contamination_scan(ws)

    summary = runner.run(
        RunConfig(condition=condition, context_budget=budget, run_seed=seed_run),
        tasks=[
            f"The workspace root is: {workspace}\nUse it verbatim (absolute Windows path) as the tool path prefix.\n\n{TASK_S1}",
            f"The workspace root is: {workspace}\nUse it verbatim (absolute Windows path) as the tool path prefix.\n\n{TASK_S2}",
        ],
        workspace=workspace,
        evaluator=make_evaluator(),
        on_session_end=after_s1,
    )
    run_dir = RESULTS / summary["run_id"]

    if summary.get("infrastructure_failure"):
        entry = {
            "run_id": summary["run_id"],
            "condition": condition,
            "budget": budget,
            "seed": seed_run,
            "experiment_commit": g["commit"],
            "infrastructure_failure": True,
            "failure": summary.get("failure"),
            "failed_at_session": summary.get("failed_at_session"),
            "success": False,
        }
        shutil.rmtree(seed, ignore_errors=True)
        shutil.rmtree(workspace, ignore_errors=True)
        return entry

    s1 = json.loads((run_dir / "session_1.json").read_text())
    s2 = json.loads((run_dir / "session_2.json").read_text())
    meta = json.loads((run_dir / "summary.json").read_text())["condition_metadata"]

    entry = {
        "run_id": summary["run_id"],
        "condition": condition,
        "budget": budget,
        "seed": seed_run,
        "experiment_commit": g["commit"],
        "s1_visible_tests_passed": s1["evaluation"]["passed"],
        "s2_all_tests_passed": s2["evaluation"]["passed"],
        "decision_leaked_to_repo": leaked.get("decision_leaked_to_repo", False),
        "notes_scrubbed": leaked.get("notes_scrubbed", []),
        "s2_context_tokens": s2["context_artifact"]["token_count"],
        "s2_context_truncated": s2["context_artifact"]["truncated"],
        "s2_agent_error": s2["agent_error"],
        "success": bool(
            s1["evaluation"]["passed"]
            and s2["evaluation"]["passed"]
            and not s2["agent_error"]
        ),
    }
    if condition == "B":
        prov = s2["context_artifact"]["provenance"]
        entry["mem0"] = {
            "returned": prov.get("memories_returned"),
            "kept": prov.get("memories_kept"),
            "sessions": [
                len(s.get("memories_added") or [])
                for s in meta.get("sessions_consumed", [])
            ],
        }

    shutil.rmtree(seed, ignore_errors=True)
    shutil.rmtree(workspace, ignore_errors=True)
    return entry


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--condition", required=True, choices=list("ABCD"))
    ap.add_argument("--budget", type=int, required=True)
    ap.add_argument("--seed", type=int, default=1)
    a = ap.parse_args()

    RESULTS.mkdir(parents=True, exist_ok=True)
    entry = run_one(a.condition, a.budget, a.seed)

    report = json.loads(SUMMARY.read_text()) if SUMMARY.exists() else {"runs": []}
    report["runs"] = [
        r for r in report["runs"]
        if not (r["condition"] == a.condition and r["budget"] == a.budget
                and r.get("seed", 1) == a.seed)
    ]
    report["runs"].append(entry)
    SUMMARY.write_text(json.dumps(report, indent=2, default=str))
    print(json.dumps(entry, indent=2, default=str), flush=True)
    return 0 if entry["success"] else 1


if __name__ == "__main__":
    sys.exit(main())
