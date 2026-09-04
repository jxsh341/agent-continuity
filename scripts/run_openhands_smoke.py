"""Milestone 0.1 smoke test.

Proves the chain:
    our runner -> OpenHands SDK -> terminal + file editor
        -> temp code workspace -> agent makes one controlled change
        -> tests -> result JSON

No memory, no conditions, no benchmark repo yet. Requires LLM_API_KEY
(and optionally LLM_MODEL / LLM_BASE_URL) in the environment.

Usage:
    .venv\\Scripts\\python scripts\\run_openhands_smoke.py
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from agent import ModelConfig, OpenHandsCodingAgent  # noqa: E402

TASK = (
    "This workspace contains a Python package `calc` with a bug: "
    "`calc/math_ops.py::add` subtracts instead of adding. "
    "Find and fix the bug with the smallest possible change, "
    "then run `python -m pytest tests/ -q` and confirm all tests pass."
)

BROKEN = "def add(a, b):\n    return a - b  # BUG\n"
TEST = (
    "from calc.math_ops import add\n\n"
    "def test_add():\n    assert add(2, 3) == 5\n"
)


def make_workspace(root: Path) -> None:
    (root / "calc").mkdir()
    (root / "calc" / "__init__.py").write_text("")
    (root / "calc" / "math_ops.py").write_text(BROKEN)
    (root / "tests").mkdir()
    (root / "tests" / "test_math_ops.py").write_text(TEST)
    (root / "pytest.ini").write_text("[pytest]\ntestpaths = tests\n")


def run_tests(workspace: Path) -> bool:
    p = subprocess.run(
        [sys.executable, "-m", "pytest", "tests/", "-q"],
        cwd=workspace,
        capture_output=True,
        text=True,
    )
    print(p.stdout[-2000:])
    return p.returncode == 0


def main() -> int:
    config = ModelConfig.from_env()
    if not config.api_key:
        print("ERROR: set LLM_API_KEY (and optionally LLM_MODEL) first.")
        return 2

    pin = json.loads(
        (Path(__file__).parent.parent / "configs" / "framework_pin.json").read_text()
    )
    adapter = OpenHandsCodingAgent(config, framework_commit=pin["commit"])

    with tempfile.TemporaryDirectory(prefix="oh_smoke_") as tmp:
        workspace = Path(tmp)
        make_workspace(workspace)
        assert not run_tests(workspace), "precondition: tests must fail before agent"

        result = adapter.run_session(task=TASK, workspace=workspace, initial_context="")

        tests_passed = run_tests(workspace)
        out = Path(__file__).parent.parent / "results" / "smoke_result.json"
        out.parent.mkdir(exist_ok=True)
        out.write_text(
            json.dumps(
                {
                    "framework_commit": result.agent_framework_commit,
                    "error": result.error,
                    "tests_passed": tests_passed,
                    "n_events": len(result.events),
                    "llm_metrics": result.llm_metrics,
                },
                indent=2,
                default=str,
            )
        )
        print(f"\ntests_passed={tests_passed}  error={result.error}")
        print(f"events={len(result.events)}  wrote {out}")
        return 0 if tests_passed and not result.error else 1


if __name__ == "__main__":
    sys.exit(main())
