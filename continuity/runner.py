"""Experiment runner: the only orchestration path for A/B/C/D.

Per session:
    artifact = condition.build_context(config.context_budget)
    result   = agent.run_session(task, workspace, artifact.text)
    condition.prepare(SessionRecord(result))

The agent receives ONLY artifact.text as initial context. The runner
persists, per session: config hash, artifact metadata, token metrics,
transcript paths, and the deterministic evaluation supplied by the
caller. Nothing conversational is shared between sessions except
via the condition object.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import time
import uuid
from pathlib import Path
from typing import Callable

from agent.openhands_adapter import CodingAgent
from conditions import CONDITIONS
from continuity.models import RunConfig
from continuity.tokens import count_tokens, truncate_lines_to_budget
from conditions.base import ContextArtifact


def enforce_budget(artifact: ContextArtifact) -> ContextArtifact:
    """Shared budget enforcement, identical for every condition.

    The condition produces the best context it wants to provide; THIS
    component applies the experimental ceiling so '2K' means the same
    thing in A/B/C/D.
    """
    if artifact.token_count <= artifact.budget_tokens:
        return artifact
    lines = artifact.text.split("\n")
    kept, _ = truncate_lines_to_budget(lines, artifact.budget_tokens, keep="newest")
    text = "\n".join(kept)
    return ContextArtifact(
        text=text,
        token_count=count_tokens(text),
        budget_tokens=artifact.budget_tokens,
        truncated=True,
        condition=artifact.condition,
        provenance={**artifact.provenance, "budgeter": "runner_enforced"},
    )


def config_hash(config: RunConfig, condition_metadata: dict, framework_pin: dict) -> str:
    blob = json.dumps(
        {
            "config": config.__dict__,
            "condition": condition_metadata,
            "framework": framework_pin,
        },
        sort_keys=True,
        default=str,
    )
    return hashlib.sha256(blob.encode()).hexdigest()


def run_pytest(workspace: Path) -> dict:
    """Default deterministic evaluator: pytest must pass."""
    p = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", "--tb=no"],
        cwd=workspace,
        capture_output=True,
        text=True,
    )
    return {
        "evaluator": "pytest",
        "passed": p.returncode == 0,
        "returncode": p.returncode,
        "tail": p.stdout[-2000:],
    }


class ExperimentRunner:
    def __init__(
        self,
        agent: CodingAgent,
        artifact_root: Path,
        framework_pin: dict,
    ):
        self.agent = agent
        self.artifact_root = artifact_root
        self.framework_pin = framework_pin

    def run(
        self,
        config: RunConfig,
        tasks: list[str],
        workspace: Path,
        evaluator: Callable[[Path, int], dict] | None = None,
        on_session_end: Callable[[int, Path], None] | None = None,
    ) -> dict:
        run_id = f"{config.condition}-{config.run_seed}-{uuid.uuid4().hex[:8]}"
        run_root = self.artifact_root / run_id
        run_root.mkdir(parents=True, exist_ok=True)
        try:
            condition = CONDITIONS[config.condition](run_root / "memory")
        except TypeError:
            condition = CONDITIONS[config.condition]()

        chash = config_hash(config, condition.metadata(), self.framework_pin)
        (run_root / "config.json").write_text(
            json.dumps(
                {"config": config.__dict__, "config_hash": chash,
                 "condition": condition.metadata(),
                 "framework": self.framework_pin},
                indent=2, default=str,
            ),
            encoding="utf-8",
        )

        sessions = []
        prev_events_hash: str | None = None
        for i, task in enumerate(tasks, start=1):
            artifact = enforce_budget(
                condition.build_context(config.context_budget, task=task)
            )
            artifact = ContextArtifact(
                **{
                    **artifact.to_dict(),
                    "provenance": {
                        **artifact.provenance,
                        # forensic identity of the exact context injected
                        "context_hash": hashlib.sha256(
                            artifact.text.encode()
                        ).hexdigest(),
                        "source_session": i - 1 if i > 1 else None,
                        "source_events_hash": prev_events_hash,
                    },
                }
            )
            started = time.perf_counter()
            result = self.agent.run_session(
                task=task, workspace=workspace, initial_context=artifact.text
            )
            elapsed = time.perf_counter() - started

            events_json = json.dumps(result.events, indent=2, default=str)
            (run_root / f"session_{i}_events.json").write_text(
                events_json, encoding="utf-8"
            )
            prev_events_hash = hashlib.sha256(events_json.encode()).hexdigest()
            (run_root / f"session_{i}_messages.json").write_text(
                json.dumps(result.messages, indent=2, default=str),
                encoding="utf-8",
            )
            eval_fn = evaluator or (lambda ws, _i: run_pytest(ws))
            evaluation = eval_fn(workspace, i)
            record = {
                "run_id": run_id,
                "config_hash": chash,
                "condition": config.condition,
                "session_index": i,
                "task": task,
                "context_artifact": artifact.to_dict(),
                "agent_error": result.error,
                "llm_metrics": result.llm_metrics,
                "wall_seconds": elapsed,
                "evaluation": evaluation,
            }
            (run_root / f"session_{i}.json").write_text(
                json.dumps(record, indent=2, default=str), encoding="utf-8"
            )
            sessions.append(record)

            if on_session_end is not None:
                on_session_end(i, workspace)
            condition.prepare(
                {
                    "session_index": i,
                    "task": task,
                    "context": artifact.text,
                    "messages": result.messages,
                    "metrics": result.llm_metrics,
                    "error": result.error,
                }
            )

        summary = {
            "run_id": run_id,
            "config_hash": chash,
            "condition": config.condition,
            "condition_metadata": condition.metadata(),
            "n_sessions": len(sessions),
            "all_evaluations_passed": all(
                s["evaluation"].get("passed") for s in sessions
            ),
        }
        (run_root / "summary.json").write_text(
            json.dumps(summary, indent=2, default=str), encoding="utf-8"
        )
        return summary
