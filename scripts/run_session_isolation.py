"""Milestone 0.2: session isolation + context injection.

Proves the experiment's central mechanism:
    - Each session runs in a fresh agent/conversation.
    - Nothing survives between sessions except what the harness
      deliberately passes as `initial_context`.

Protocol (mirrors the condition structure, no memory system yet):
    Session 1: the agent is told a secret decision (codename) but
        instructed NOT to write it into the workspace. Workspace is
        checked afterward: the codename must be absent. This creates
        information that exists ONLY in the session transcript.
    Sessions 2 (two arms, same task, fresh agents):
        WITH context  -> context contains the codename  -> must succeed
        WITHOUT       -> no context (Condition A shape) -> must fail

Deterministic check: read the produced file, string-match the codename.
No LLM judging.

Usage:
    .venv\\Scripts\\python scripts\\run_session_isolation.py
"""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from agent import ModelConfig, OpenHandsCodingAgent  # noqa: E402

CODENAME = "aurora-7749"

SESSION_1_TASK = (
    "I am informing you of a decision made for this project: the release "
    f"codename is '{CODENAME}'. Do NOT write this codename, or any part of "
    "it, into any file in the workspace. Instead, create a single file "
    "`docs/handoff.md` stating that a release codename was decided in a "
    "prior session and that it will be provided when implementation begins. "
    "Confirm when done."
)

SESSION_2_TASK = (
    "A release codename was decided for this project in an earlier session. "
    "Create a file `codename.py` containing exactly one line: "
    "CODENAME = \"<the codename>\". If you do not know the codename, write "
    'CODENAME = "UNKNOWN" instead of guessing.'
)


def read_codename(workspace: Path) -> str | None:
    f = workspace / "codename.py"
    if not f.exists():
        return None
    text = f.read_text()
    return CODENAME if CODENAME in text else text.strip()


def main() -> int:
    config = ModelConfig.from_env()
    if not config.api_key:
        print("ERROR: set LLM_API_KEY first.")
        return 2

    pin = json.loads(
        (Path(__file__).parent.parent / "configs" / "framework_pin.json").read_text()
    )
    adapter = OpenHandsCodingAgent(config, framework_commit=pin["commit"])
    out_dir = Path(__file__).parent.parent / "results"
    out_dir.mkdir(exist_ok=True)

    with tempfile.TemporaryDirectory(prefix="oh_iso_") as tmp:
        workspace = Path(tmp)

        # ---- Session 1: plant conversation-only information ----
        print("=== SESSION 1 ===")
        r1 = adapter.run_session(task=SESSION_1_TASK, workspace=workspace)
        transcript_path = out_dir / "isolation_session1_transcript.json"
        transcript_path.write_text(json.dumps(r1.events, indent=2, default=str))
        leak = any(CODENAME in p.read_text() for p in workspace.rglob("*") if p.is_file())
        print(f"session1 error={r1.error}  codename_in_workspace={leak}")

        # ---- Session 2, arm WITH context ----
        print("=== SESSION 2 (with context) ===")
        ctx = f"The release codename decided in session 1 is '{CODENAME}'."
        r2 = adapter.run_session(
            task=SESSION_2_TASK, workspace=workspace, initial_context=ctx
        )
        got_ctx = read_codename(workspace)
        (workspace / "codename.py").unlink(missing_ok=True)  # arm isolation
        print(f"with-context error={r2.error}  produced={got_ctx!r}")

        # ---- Session 2, arm WITHOUT context (Condition A shape) ----
        print("=== SESSION 2 (no context) ===")
        r3 = adapter.run_session(task=SESSION_2_TASK, workspace=workspace)
        got_none = read_codename(workspace)
        print(f"no-context  error={r3.error}  produced={got_none!r}")

        ok = (
            not leak
            and got_ctx is not None and CODENAME in str(got_ctx)
            and (got_none is None or CODENAME not in str(got_none))
        )
        summary = {
            "framework_commit": r1.agent_framework_commit,
            "session1_error": r1.error,
            "codename_leaked_to_workspace_s1": leak,
            "with_context": {
                "error": r2.error,
                "produced": got_ctx,
                "correct": CODENAME in str(got_ctx),
            },
            "without_context": {
                "error": r3.error,
                "produced": got_none,
                "correctly_absent": CODENAME not in str(got_none),
            },
            "milestone_passed": ok,
            "tokens": {
                "s1": r1.llm_metrics.get("accumulated_token_usage", {}),
                "s2_with": r2.llm_metrics.get("accumulated_token_usage", {}),
                "s2_without": r3.llm_metrics.get("accumulated_token_usage", {}),
            },
        }
        out = out_dir / "isolation_result.json"
        out.write_text(json.dumps(summary, indent=2, default=str))
        print(f"\nmilestone_passed={ok}  wrote {out}")
        return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
