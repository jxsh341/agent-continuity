"""Milestone 0.4 validation: Condition B across a hard session boundary.

Two distinct checks, deliberately separated:

  ADAPTER CHECK (mechanical): does the condition's context artifact
      contain the planted fact?  Must hold for B and D, must fail for A.

  AGENT-LEVEL recovery (the actual experimental measurement): does the
      fresh S2 agent produce the fact?  Conditions may legitimately
      differ here -- e.g. Mem0 stores stale session-scoped prohibitions
      next to facts, and the agent may obey them. That is B behaving
      like B, not a harness bug.

Arms are run independently (see --arms) because full agent sessions are
slow; results are merged into results/condition_b_validation.json.

Part 2 (adversarial): S1 receives 12 facts; S2 is queried for ONE.
Reports transcript tokens -> stored items -> retrieved items -> context
tokens (compression) plus target recall.

Usage:
    .venv\\Scripts\\python scripts\\run_condition_b_isolation.py --arms A,D
    .venv\\Scripts\\python scripts\\run_condition_b_isolation.py --arms B
    .venv\\Scripts\\python scripts\run_condition_b_isolation.py --adversarial
"""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from agent import ModelConfig, OpenHandsCodingAgent  # noqa: E402
from continuity.models import RunConfig  # noqa: E402
from continuity.runner import ExperimentRunner  # noqa: E402
from continuity.tokens import count_tokens  # noqa: E402

CODENAME = "aurora-7749"
OUT = Path(__file__).parent.parent / "results" / "condition_b_validation.json"

S1_PLANT = (
    "I am informing you of a decision made for this project: the release "
    f"codename is '{CODENAME}'. Do NOT write this codename, or any part of "
    "it, into any file in the workspace. Create a file `docs/handoff.md` "
    "stating only that a release codename was decided in a prior session "
    "and will be provided when implementation begins. Confirm when done."
)

S2_ASK = (
    "A release codename was decided for this project in an earlier session. "
    "The earlier instruction not to write it down applied to that session "
    "only; it no longer applies. Create a file `codename.py` containing "
    "exactly one line: CODENAME = \"<the codename>\". If you do not know "
    'the codename, write CODENAME = "UNKNOWN" instead of guessing.'
)

ADV_FACTS = [
    ("target", "the maximum retry budget for pipeline workers is 17"),
    ("decoy", "the staging cluster region is eu-west-3"),
    ("decoy", "the preferred JSON indent style is 2 spaces"),
    ("decoy", "the deployment window is Tuesdays 02:00-04:00 UTC"),
    ("decoy", "the log retention period is 45 days"),
    ("decoy", "the cache TTL for session tokens is 900 seconds"),
    ("decoy", "the naming scheme for feature flags is kebab-case"),
    ("decoy", "the maximum request payload size is 4 MiB"),
    ("decoy", "the on-call rotation changes on Mondays"),
    ("decoy", "the build sandbox has 8 vCPUs"),
    ("decoy", "the memory limit for workers is 3 GiB"),
    ("decoy", "the default branch is renamed to 'trunk'"),
]
ADV_TARGET_ANSWER = "17"

ADV_S1 = (
    "I am informing you of several standing project facts decided earlier. "
    "Do NOT write any of them into the workspace; they must remain outside "
    "the repository. Create `docs/handoff.md` noting that operational facts "
    "were communicated previously. The facts are:\n"
    + "\n".join(f"- {f}" for _, f in ADV_FACTS)
    + "\nConfirm when done."
)

ADV_S2 = (
    "Based on the previously communicated project facts, create a file "
    "`retry_config.py` containing exactly one line: "
    "MAX_RETRIES = <the maximum retry budget for pipeline workers>. "
    "The earlier instruction not to write facts down no longer applies. "
    'If you do not know it, write MAX_RETRIES = "UNKNOWN".'
)


def no_eval(workspace, session_index):
    return {"evaluator": "none", "passed": True}


def read_answer(workspace: Path, filename: str) -> str:
    p = workspace / filename
    return p.read_text() if p.exists() else ""


def run_arms(arms: list[str]) -> None:
    config = ModelConfig.from_env()
    pin = json.loads(
        (Path(__file__).parent.parent / "configs" / "framework_pin.json").read_text()
    )
    results_root = Path(__file__).parent.parent / "results"
    report = {}
    out = results_root / "condition_b_validation.json"
    if out.exists():
        report = json.loads(out.read_text())
    report.setdefault("part1_isolation", {})

    for cond in arms:
        with tempfile.TemporaryDirectory(prefix=f"oh_b_iso_{cond}_") as tmp:
            ws = Path(tmp)
            agent = OpenHandsCodingAgent(config, framework_commit=pin["commit"])
            runner = ExperimentRunner(agent, results_root, framework_pin=pin)
            summary = runner.run(
                RunConfig(condition=cond, context_budget=2048, run_seed=1),
                tasks=[S1_PLANT, S2_ASK], workspace=ws, evaluator=no_eval,
            )
            run_dir = results_root / summary["run_id"]
            s2 = json.loads((run_dir / "session_2.json").read_text())
            answer = read_answer(ws, "codename.py")
            ctx_text = s2["context_artifact"]["text"]
            entry = {
                "run_id": summary["run_id"],
                "fact_in_context_artifact": CODENAME in ctx_text,
                "codename_recovered": CODENAME in answer,
                "s2_context_tokens": s2["context_artifact"]["token_count"],
                "s2_agent_error": s2["agent_error"],
            }
            report["part1_isolation"][cond] = entry
            print(f"[part1] {cond}: in_ctx={entry['fact_in_context_artifact']} "
                  f"recovered={entry['codename_recovered']}", flush=True)
    report["part1_passed"] = (
        not report["part1_isolation"]["A"]["codename_recovered"]
        and report["part1_isolation"]["B"]["codename_recovered"]
        and report["part1_isolation"]["D"]["codename_recovered"]
    ) if all(c in report["part1_isolation"] for c in "ABD") else None
    out.write_text(json.dumps(report, indent=2, default=str))
    print(f"wrote {out}", flush=True)


def run_adversarial() -> None:
    config = ModelConfig.from_env()
    pin = json.loads(
        (Path(__file__).parent.parent / "configs" / "framework_pin.json").read_text()
    )
    results_root = Path(__file__).parent.parent / "results"
    with tempfile.TemporaryDirectory(prefix="oh_b_adv_") as tmp:
        ws = Path(tmp)
        agent = OpenHandsCodingAgent(config, framework_commit=pin["commit"])
        runner = ExperimentRunner(agent, results_root, framework_pin=pin)
        summary = runner.run(
            RunConfig(condition="B", context_budget=2048, run_seed=1),
            tasks=[ADV_S1, ADV_S2], workspace=ws, evaluator=no_eval,
        )
        run_dir = results_root / summary["run_id"]
        s2 = json.loads((run_dir / "session_2.json").read_text())
        answer = read_answer(ws, "retry_config.py")
        s1_events = json.loads((run_dir / "session_1_events.json").read_text())
        s1_transcript_tokens = sum(count_tokens(json.dumps(x)) for x in s1_events)
        meta = json.loads((run_dir / "summary.json").read_text())["condition_metadata"]
        prov = s2["context_artifact"]["provenance"]
        target_in_ctx = any(
            ADV_TARGET_ANSWER in (r or "")
            for r in [s2["context_artifact"]["text"]]
        )
        correct = ADV_TARGET_ANSWER in answer and "UNKNOWN" not in answer
        entry = {
            "run_id": summary["run_id"],
            "target_in_context_artifact": target_in_ctx,
            "target_recovered": correct,
            "answer": answer.strip()[:200],
            "s1_raw_transcript_tokens": s1_transcript_tokens,
            "mem0_items_stored": [
                len(s.get("memories_added") or [])
                for s in meta["sessions_consumed"]
            ],
            "memories_returned": prov.get("memories_returned"),
            "memories_kept": prov.get("memories_kept"),
            "s2_context_tokens": s2["context_artifact"]["token_count"],
            "compression_s1raw_to_ctx": round(
                s2["context_artifact"]["token_count"]
                / max(1, s1_transcript_tokens), 4),
        }
        out = results_root / "condition_b_validation.json"
        report = json.loads(out.read_text()) if out.exists() else {}
        report["part2_adversarial"] = entry
        report["part2_target_recovered"] = entry["target_recovered"]
        out.write_text(json.dumps(report, indent=2, default=str))
        print(json.dumps(entry, indent=2, default=str), flush=True)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--arms", type=str, default="")
    ap.add_argument("--adversarial", action="store_true")
    a = ap.parse_args()
    if a.arms:
        run_arms([x.strip().upper() for x in a.arms.split(",") if x.strip()])
    if a.adversarial:
        run_adversarial()
