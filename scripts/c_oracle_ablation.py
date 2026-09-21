"""Oracle-C arm (diagnostic, Phase 4B): verified canonical state -> S2.

Feeds a ground-truth C-v0.1 state (from extraction.gold_state, derived from the
frozen benchmark CRITICAL_FACTS) through the FROZEN serializer as the S2 context.
Skips the S1 agent (reference S1 applied deterministically). Isolates
representation+execution from extraction. NOT one of the competitive systems.

Ledger: same per-benchmark summary.json, condition="O". Exit codes:
0 = success, 1 = valid failure, 3 = provider failure (AMD-005).

Usage:
    .venv\\Scripts\\python scripts\\c_oracle_ablation.py \\
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


def classify_provider_error(err: str | None) -> str | None:
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


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--benchmark", required=True, choices=list(BENCHMARKS))
    ap.add_argument("--budget", type=int, default=2048)
    ap.add_argument("--seed", type=int, default=1)
    a = ap.parse_args()

    bench = BENCHMARKS[a.benchmark]
    out_root = ROOT / "results" / "phase4_oracle" / a.benchmark
    out_root.mkdir(parents=True, exist_ok=True)

    g = json.loads((ROOT / "configs" / "framework_pin.json").read_text())
    config = ModelConfig.from_env()

    seed = Path(tempfile.mkdtemp(prefix=f"o4_{a.benchmark}_seed_"))
    bench.make_seed(seed)
    ws = Path(tempfile.mkdtemp(prefix=f"o4_{a.benchmark}_ws_"))
    shutil.copytree(seed, ws, dirs_exist_ok=True)
    bench.apply_s1_reference(ws)

    state = gold_state(a.benchmark)
    text = serialize_full(state)
    fidelity = gold_to_c_fidelity(a.benchmark, text)

    # GATE: gold->C fidelity must be 100% before any S2 runs.
    if not all(fidelity.values()):
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

    provider_err = classify_provider_error(result.error)
    if provider_err:
        infra_file = out_root / "infra.jsonl"
        with open(infra_file, "a", encoding="utf-8") as f:
            f.write(json.dumps({
                "benchmark": a.benchmark, "budget": a.budget, "seed": a.seed,
                "classification": provider_err,
                "detail": (result.error or "")[:300],
            }, default=str) + "\n")
        print(json.dumps({"classification": provider_err}, indent=2))
        shutil.rmtree(seed, ignore_errors=True)
        shutil.rmtree(ws, ignore_errors=True)
        return 3

    bench.inject_hidden_tests(ws)
    ev = pytest_run(ws)

    entry = {
        "run_id": result.__dict__.get("task", "")[:0] or f"O-{a.benchmark}-{a.budget}-{a.seed}",
        "benchmark": a.benchmark,
        "condition": "O",
        "budget": a.budget,
        "seed": a.seed,
        "experiment_commit": g.get("experiment_repo", {}).get("baseline_commit", ""),
        "gold_to_c_fidelity": fidelity,
        "context_tokens": count_tokens(text),
        "context_budget": a.budget,
        "agent_error": result.error,
        "s2_hidden_tests_passed": ev["passed"],
        "eval_tail": ev["tail"],
        "success": bool(ev["passed"] and not result.error),
    }
    summary_file = out_root / "summary.json"
    _upsert_summary(summary_file, entry)
    print(json.dumps(entry, indent=2, default=str))

    shutil.rmtree(seed, ignore_errors=True)
    shutil.rmtree(ws, ignore_errors=True)
    return 0 if entry["success"] else 1


def _upsert_summary(summary_file: Path, entry: dict) -> None:
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