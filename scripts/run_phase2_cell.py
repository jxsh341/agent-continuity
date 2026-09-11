"""Phase 2 cell runner: reliable-extraction (gold) C representation, S2-only.

For one (benchmark, budget, seed): apply reference S1, build gold C-v0.1 state,
verify gold->C fidelity (100% required), serialize via the FROZEN serializer,
run a single fresh S2 agent with that context, inject hidden tests, evaluate.

No LLM extraction. Frozen C schema/serializer/agent/task/evaluator.

Usage:
    .venv\\Scripts\\python scripts\\run_phase2_cell.py \\
        --benchmark fastapi --budget 2048 --seed 1
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
from extraction.gold_state import gold_state, gold_to_c_fidelity  # noqa: E402
from serialization.c_serializer import serialize_full  # noqa: E402

ROOT = Path(__file__).parent.parent


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
    ap.add_argument("--seed", type=int, default=1)
    a = ap.parse_args()

    bench = BENCHMARKS[a.benchmark]
    out_root = ROOT / "results" / "phase2" / a.benchmark
    out_root.mkdir(parents=True, exist_ok=True)

    g = json.loads((ROOT / "configs" / "framework_pin.json").read_text())
    config = ModelConfig.from_env()

    seed = Path(tempfile.mkdtemp(prefix=f"p2_{a.benchmark}_seed_"))
    bench.make_seed(seed)
    ws = Path(tempfile.mkdtemp(prefix=f"p2_{a.benchmark}_ws_"))
    shutil.copytree(seed, ws, dirs_exist_ok=True)
    bench.apply_s1_reference(ws)

    state = gold_state(a.benchmark)
    text = serialize_full(state)
    fidelity = gold_to_c_fidelity(a.benchmark, text)
    all_faithful = all(fidelity.values())

    # GATE: gold->C fidelity must be 100% before any S2 runs.
    if not all_faithful:
        entry = {
            "benchmark": a.benchmark, "budget": a.budget, "seed": a.seed,
            "gold_to_c_fidelity_failed": fidelity,
            "aborted_before_s2": True,
        }
        (out_root / f"abort_{a.seed}_{a.budget}.json").write_text(
            json.dumps(entry, indent=2))
        print(json.dumps(entry, indent=2))
        shutil.rmtree(seed, ignore_errors=True)
        shutil.rmtree(ws, ignore_errors=True)
        return 1

    hint = (
        f"The workspace root is: {ws}\n"
        "Use it verbatim (absolute Windows path) as the tool path prefix.\n\n"
    )
    task = hint + bench.TASK_S2

    agent = OpenHandsCodingAgent(config, framework_commit=g["commit"])
    result = agent.run_session(task=task, workspace=ws, initial_context=text)

    bench.inject_hidden_tests(ws)
    ev = pytest_run(ws)

    entry = {
        "benchmark": a.benchmark,
        "budget": a.budget,
        "seed": a.seed,
        "gold_to_c_fidelity": fidelity,
        "context_tokens": count_tokens(text),
        "context_budget": a.budget,
        "agent_error": result.error,
        "s2_hidden_tests_passed": ev["passed"],
        "eval_tail": ev["tail"],
    }
    (out_root / f"cell_{a.seed}_{a.budget}.json").write_text(
        json.dumps(entry, indent=2))
    print(json.dumps(entry, indent=2, default=str))

    shutil.rmtree(seed, ignore_errors=True)
    shutil.rmtree(ws, ignore_errors=True)
    return 0 if ev["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())