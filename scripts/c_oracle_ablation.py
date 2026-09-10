"""C-oracle ablation (exploratory): feed a MANUALLY-VERIFIED structured state
as the S2 context, bypassing the frozen extractor entirely, to isolate
"representation vs extraction".

Not part of the A/B/C/D score. Builds ground-truth C state from the benchmark's
critical facts, serializes it, and runs the S2 agent once. If C-oracle succeeds
where C-frozen failed on a benchmark, the bottleneck is extraction, not the
structured representation.

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
from continuity.models import RunConfig  # noqa: E402
from continuity.runner import ExperimentRunner  # noqa: E402

# Ground-truth oracle state per benchmark (the "right answer", written by hand).
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


class OracleCondition:
    """A ContinuityCondition that always returns a fixed, verified state."""

    name = "C"

    def __init__(self, state: dict):
        from serialization.c_serializer import serialize_full
        self._text = serialize_full(state)

    def prepare(self, previous_session):
        pass

    def build_context(self, budget_tokens, task=None):
        from conditions.base import ContextArtifact
        from continuity.tokens import count_tokens
        return ContextArtifact(
            text=self._text, token_count=count_tokens(self._text),
            budget_tokens=budget_tokens, truncated=False,
            condition="C-oracle", provenance={"kind": "oracle"},
        )

    def metadata(self):
        return {"condition": "C-oracle"}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--benchmark", required=True, choices=list(BENCHMARKS))
    ap.add_argument("--budget", type=int, default=2048)
    ap.add_argument("--seed", type=int, default=1)
    a = ap.parse_args()

    bench = BENCHMARKS[a.benchmark]
    out_root = Path("results") / f"oracle_{a.benchmark}"
    out_root.mkdir(parents=True, exist_ok=True)

    g = json.loads((Path("configs/framework_pin.json")).read_text())
    config = ModelConfig.from_env()
    agent = OpenHandsCodingAgent(config, framework_commit=g["commit"])
    runner = ExperimentRunner(agent, out_root, framework_pin=g)

    seed = Path(tempfile.mkdtemp(prefix=f"oracle_{a.benchmark}_seed_"))
    bench.make_seed(seed)
    ws = Path(tempfile.mkdtemp(prefix=f"oracle_{a.benchmark}_ws_"))
    shutil.copytree(seed, ws, dirs_exist_ok=True)

    import conditions as conditions_pkg
    oracle = OracleCondition(ORACLE_STATE[a.benchmark])
    orig = conditions_pkg.CONDITIONS["C"]
    conditions_pkg.CONDITIONS["C"] = lambda *a, **k: oracle
    try:
        summary = runner.run(
            RunConfig(condition="C", context_budget=a.budget, run_seed=a.seed),
            tasks=[bench.TASK_S1, bench.TASK_S2],
            workspace=ws,
            evaluator=lambda ws, idx: ({"passed": True}
                                       if idx == 1 else
                                       (bench.inject_hidden_tests(ws), pytest_run(ws))[1]),
        )
    finally:
        conditions_pkg.CONDITIONS["C"] = orig

    print(json.dumps(summary, indent=2, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())