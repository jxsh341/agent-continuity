"""Milestone 0.3: Condition D through the full pipeline, for real.

Pipeline under test (per budget):
    S1 (engineering task) -> transcript -> Condition D -> budget artifact
        -> fresh S2 (dependent engineering task) -> pytest -> results/

Budgets: 2048, 4096, 8192 tokens. Each budget gets its own fresh
workspace reset from the same seed, so runs are comparable.

Note: the repo persists across sessions, so this is a PLUMBING test,
not a memory-efficacy result. The benchmark (information that only
exists in-session) comes later.
"""

from __future__ import annotations

import json
import shutil
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from agent import ModelConfig, OpenHandsCodingAgent  # noqa: E402
from continuity.models import RunConfig  # noqa: E402
from continuity.runner import ExperimentRunner, run_pytest  # noqa: E402

BUDGETS = [2048, 4096, 8192]

SEED_FILES = {
    "pytest.ini": "[pytest]\ntestpaths = tests\n",
    "textutil/__init__.py": "",
    "textutil/slug.py": (
        "# Feature A is implemented in session 1.\n"
    ),
    "tests/test_slug.py": (
        "from textutil.slug import slugify\n\n"
        "def test_slugify_basic():\n"
        "    assert slugify('Hello World!') == 'hello-world'\n\n"
        "def test_slugify_whitespace_and_case():\n"
        "    assert slugify('  Data  PIPELINE v2 ') == 'data-pipeline-v2'\n"
    ),
    "tests/test_filename.py": (
        "from textutil.slug import title_to_filename\n\n"
        "def test_title_to_filename_md():\n"
        "    assert title_to_filename('My Report Draft') == 'my-report-draft.md'\n"
    ),
}

SEED_README = (
    "textutil package. Conventions: lowercase, words joined with '-', "
    "strip punctuation, collapse whitespace. All public functions live "
    "in textutil/slug.py.\n"
)

TASK_S1 = (
    "Implement feature A: `slugify(text)` in textutil/slug.py following the "
    "package conventions in README.md. Run the slug tests; they must pass. "
    "Do not implement title_to_filename yet."
)

TASK_S2 = (
    "Implement feature B: `title_to_filename(title)` in textutil/slug.py. "
    "It must reuse this package's existing slug behavior and return the "
    "slug with a '.md' suffix. All tests must pass."
)


def make_seed(root: Path) -> None:
    for rel, content in SEED_FILES.items():
        p = root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content)
    (root / "README.md").write_text(SEED_README)


def make_evaluator() -> callable:
    """Session 1 is only required to keep the slug tests green
    (feature-B tests reference code that intentionally doesn't exist
    until session 2). Session 2+ must keep the whole suite green."""

    def _eval(workspace: Path, session_index: int) -> dict:
        if session_index == 1:
            import subprocess

            p = subprocess.run(
                [sys.executable, "-m", "pytest", "-q", "--tb=no", "tests/test_slug.py"],
                cwd=workspace, capture_output=True, text=True,
            )
            return {"evaluator": "pytest:tests/test_slug.py",
                    "passed": p.returncode == 0,
                    "returncode": p.returncode, "tail": p.stdout[-2000:]}
        return run_pytest(workspace)

    return _eval


def main() -> int:
    config = ModelConfig.from_env()
    if not config.api_key:
        print("ERROR: set LLM_API_KEY first.")
        return 2

    pin_path = Path(__file__).parent.parent / "configs" / "framework_pin.json"
    pin = json.loads(pin_path.read_text())
    agent = OpenHandsCodingAgent(config, framework_commit=pin["commit"])
    results_root = Path(__file__).parent.parent / "results"

    seed = Path(tempfile.mkdtemp(prefix="oh_d_seed_"))
    make_seed(seed)

    outcomes = {}
    ok = True
    for budget in BUDGETS:
        print(f"===== budget={budget} starting =====", flush=True)
        workspace = Path(tempfile.mkdtemp(prefix=f"oh_d_{budget}_"))
        shutil.copytree(seed, workspace, dirs_exist_ok=True)
        runner = ExperimentRunner(agent, results_root, framework_pin=pin)
        summary = runner.run(
            RunConfig(condition="D", context_budget=budget, run_seed=1),
            tasks=[TASK_S1, TASK_S2],
            workspace=workspace,
            evaluator=make_evaluator(),
        )
        run_dir = results_root / summary["run_id"]
        s2 = json.loads((run_dir / "session_2.json").read_text())
        outcomes[budget] = {
            "run_id": summary["run_id"],
            "all_passed": summary["all_evaluations_passed"],
            "s2_context_tokens": s2["context_artifact"]["token_count"],
            "s2_context_truncated": s2["context_artifact"]["truncated"],
            "s2_agent_error": s2["agent_error"],
        }
        ok = ok and summary["all_evaluations_passed"] and not s2["agent_error"]
        print(
            f"budget={budget}  passed={summary['all_evaluations_passed']}  "
            f"s2_ctx_tokens={outcomes[budget]['s2_context_tokens']}  "
            f"truncated={outcomes[budget]['s2_context_truncated']}  "
            f"error={s2['agent_error']}"
        , flush=True)

    out = results_root / "milestone_0_3_d.json"
    out.write_text(json.dumps(outcomes, indent=2, default=str))
    print(f"\nmilestone_passed={ok}  wrote {out}")
    shutil.rmtree(seed, ignore_errors=True)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
