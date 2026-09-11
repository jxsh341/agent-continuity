"""C-oracle ablation (exploratory), Option B: S2-only.

Skips the S1 agent entirely (its output is discarded in the oracle) and instead
applies a deterministic reference S1 implementation. Then runs ONLY the S2
agent with a manually-verified ground-truth C state as its context.

Isolates: "given correct structured state, can the downstream S2 agent use it?"

Not part of the A/B/C/D score. Does not change C schema/serializer/prompt,
agent model, task wording, benchmark, evaluator, prioritization, or budget.

Usage:
    .venv\\Scripts\\python scripts\\c_oracle_ablation.py --benchmark config_env
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
from continuity.tokens import count_tokens  # noqa: E402
from serialization.c_serializer import serialize_full  # noqa: E402

ORACLE_STATE = {
    "fastapi": {
        "decisions": [
            {"id": "DEC-001", "decision": "reports endpoint path is /reports/summary",
             "reason": "team design", "status": "active"},
            {"id": "DEC-002", "decision": "response shape is {'reports': [{'category': str, 'count': int}], 'page_size': 7}",
             "reason": "team design", "status": "active"},
        ],
    },
    "schema_migration": {
        "decisions": [
            {"id": "DEC-001", "decision": "next migration filename is 003_add_audit_log.sql",
             "reason": "team design", "status": "active"},
            {"id": "DEC-002", "decision": "migration creates table audit_log with columns id (INTEGER PRIMARY KEY), event (TEXT), created_at (INTEGER)",
             "reason": "team design", "status": "active"},
        ],
    },
    "config_env": {
        "decisions": [
            {"id": "DEC-001", "decision": "environment variable SHOPAPI_RATE_LIMIT_RPS feeds config key rate_limit_rps with intended value 42",
             "reason": "deploy decision", "status": "active"},
        ],
    },
}


def pytest_run(ws: Path) -> dict:
    p = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", "--tb=no", "tests/"],
        cwd=ws, capture_output=True, text=True,
    )
    return {"passed": p.returncode == 0, "tail": p.stdout[-1500:]}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--benchmark", required=True, choices=list(BENCHMARKS))
    ap.add_argument("--budget", type=int, default=2048)
    a = ap.parse_args()

    bench = BENCHMARKS[a.benchmark]
    out_root = Path("results") / f"oracle_{a.benchmark}"
    out_root.mkdir(parents=True, exist_ok=True)

    g = json.loads(Path("configs/framework_pin.json").read_text())
    config = ModelConfig.from_env()

    seed = Path(tempfile.mkdtemp(prefix=f"oracle_{a.benchmark}_seed_"))
    bench.make_seed(seed)
    ws = Path(tempfile.mkdtemp(prefix=f"oracle_{a.benchmark}_ws_"))
    shutil.copytree(seed, ws, dirs_exist_ok=True)
    bench.apply_s1_reference(ws)

    oracle_text = serialize_full(ORACLE_STATE[a.benchmark])
    hint = (
        f"The workspace root is: {ws}\n"
        "Use it verbatim (absolute Windows path) as the tool path prefix.\n\n"
    )
    task = hint + bench.TASK_S2

    agent = OpenHandsCodingAgent(config, framework_commit=g["commit"])
    result = agent.run_session(task=task, workspace=ws, initial_context=oracle_text)

    bench.inject_hidden_tests(ws)
    ev = pytest_run(ws)

    entry = {
        "benchmark": a.benchmark,
        "oracle_tokens": count_tokens(oracle_text),
        "agent_error": result.error,
        "s2_hidden_tests_passed": ev["passed"],
        "eval_tail": ev["tail"],
    }
    (out_root / "result.json").write_text(json.dumps(entry, indent=2))
    print(json.dumps(entry, indent=2, default=str))

    shutil.rmtree(seed, ignore_errors=True)
    shutil.rmtree(ws, ignore_errors=True)
    return 0 if ev["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())