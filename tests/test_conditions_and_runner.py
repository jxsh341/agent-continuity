"""Offline harness tests: no LLM, no network. Uses a FakeAgent."""

import json

import pytest

from agent.models import AgentSessionResult
from conditions import CONDITIONS, ConditionA, ConditionD
from continuity.models import RunConfig
from continuity.runner import ExperimentRunner
from continuity.tokens import count_tokens


class FakeAgent:
    """CodingAgent-protocol stub: echoes and fabricates a transcript."""

    def __init__(self):
        self.calls = []

    def run_session(self, task, workspace, initial_context=""):
        self.calls.append(initial_context)
        r = AgentSessionResult(
            task=task, workspace=str(workspace), initial_context=initial_context
        )
        r.messages = [
            {"role": "user", "content": task},
            {"role": "assistant", "content": f"did work on: {task}"},
        ]
        r.llm_metrics = {"accumulated_token_usage": {"prompt_tokens": 1}}
        return r


def eval_ok(workspace, session_index=1):
    return {"evaluator": "fake", "passed": True}


# --- condition contract -------------------------------------------------

def test_conditions_share_interface():
    for name, cls in CONDITIONS.items():
        cond = cls()
        artifact = cond.build_context(512)
        assert artifact.condition == name
        assert artifact.token_count == count_tokens(artifact.text)
        assert artifact.token_count <= 512
        assert isinstance(cond.metadata(), dict)


def test_a_drops_everything():
    a = ConditionA()
    a.prepare({"session_index": 1, "messages": [{"role": "user", "content": "x"}]})
    assert a.build_context(1024).text == ""


def test_d_returns_history_within_budget():
    d = ConditionD()
    d.prepare({
        "session_index": 1,
        "messages": [{"role": "user", "content": "task one"},
                     {"role": "assistant", "content": "did one"}],
    })
    artifact = d.build_context(4096)
    assert "task one" in artifact.text and "did one" in artifact.text
    assert not artifact.truncated


def test_d_truncates_oldest_first():
    d = ConditionD()
    d.prepare({
        "session_index": 1,
        "messages": [{"role": "user", "content": "OLD " * 400},
                     {"role": "assistant", "content": "RECENT"}],
    })
    artifact = d.build_context(64)
    assert artifact.truncated
    assert "RECENT" in artifact.text
    assert artifact.token_count <= 64


def test_b_empty_before_any_prepare():
    b = CONDITIONS["B"]()
    artifact = b.build_context(512, task="what happened before?")
    assert artifact.text == "" and artifact.token_count == 0
    assert artifact.provenance["system"] == "mem0 2.0.19"


def test_c_empty_before_any_prepare():
    c = CONDITIONS["C"]()
    artifact = c.build_context(1024)
    assert artifact.text == "" and "extraction_error" in artifact.provenance


# --- runner plumbing -----------------------------------------------------

def test_runner_end_to_end(tmp_path):
    agent = FakeAgent()
    runner = ExperimentRunner(agent, tmp_path / "results", framework_pin={"commit": "x"})
    summary = runner.run(
        RunConfig(condition="D", context_budget=2048, run_seed=1),
        tasks=["impl feature A", "extend with feature B"],
        workspace=tmp_path,
        evaluator=eval_ok,
    )
    assert summary["all_evaluations_passed"]
    assert summary["n_sessions"] == 2
    # Session 1 got empty context; session 2 got session-1 history.
    assert agent.calls[0] == ""
    assert "impl feature A" in agent.calls[1]
    # Artifacts persisted with config hash.
    s2 = json.loads(
        (tmp_path / "results" / summary["run_id"] / "session_2.json").read_text()
    )
    assert s2["config_hash"] == summary["config_hash"]
    assert s2["context_artifact"]["token_count"] <= 2048
    assert (tmp_path / "results" / summary["run_id"] / "session_1_events.json").exists()


def test_runner_never_leaks_under_condition_a(tmp_path):
    agent = FakeAgent()
    runner = ExperimentRunner(agent, tmp_path / "results", framework_pin={})
    runner.run(RunConfig(condition="A"), ["t1", "t2"], tmp_path, eval_ok)
    assert agent.calls == ["", ""]
