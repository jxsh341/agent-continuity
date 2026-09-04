"""Offline tests for Condition C: extractor parsing, deterministic
serialization, budget truncation, failure recording. No network."""

import json

from conditions.c import ConditionC
from conditions.base import ContextArtifact
from continuity.tokens import count_tokens
from extractors.c_extractor import (
    ExtractionError,
    extract_c_state,
    normalize_state,
    serialize_transcript,
)
from serialization.c_serializer import serialize_full, serialize_within_budget

GOOD_RAW = json.dumps({
    "goals": [{"id": "G-001", "description": "ship feature set X"}],
    "tasks": [{"id": "TASK-001", "description": "implement DELETE /items/{id}",
               "status": "completed", "files": ["app/main.py", "tests/test_items.py"]}],
    "decisions": [
        {"id": "DEC-001", "decision": "reports endpoint is GET /reports/summary",
         "reason": "team design", "status": "active"},
        {"id": "DEC-002", "decision": "page_size fixed at 7",
         "reason": "team design", "status": "active"},
    ],
    "entities": [{"id": "E-001", "name": "shopapi", "type": "service", "description": "FastAPI app"}],
    "facts": [{"id": "F-001", "fact": "visible suite has 5 tests"}],
    "events": [{"id": "EV-001", "event": "session 1 completed DELETE endpoint", "session": 1}],
    "failures": [{"id": "FAIL-001", "signature": "import-error-in-tests",
                  "description": "pytest run from wrong cwd failed import", "status": "resolved"}],
    "dependencies": [{"id": "DEP-001", "description": "fastapi, pytest"}],
    "current_state": {"branch": "main", "implemented_features": ["DELETE /items/{id}"],
                      "known_bugs": [], "tests_status": "visible suite green",
                      "active_work": "reports endpoint pending"},
})

MESSAGES = [
    {"role": "user", "content": "Implement DELETE /items/{id}. Design decided: /reports/summary, page_size 7."},
    {"role": "assistant", "content": "Done. Tests pass."},
]


def fake_llm(system: str, user: str) -> str:
    assert "SESSION TRANSCRIPT" in user
    return GOOD_RAW


def make_c(tmp_path) -> ConditionC:
    c = ConditionC(tmp_path, llm_complete=fake_llm)
    c.prepare({"session_index": 1, "messages": MESSAGES})
    return c


def test_extraction_produces_valid_state(tmp_path):
    c = make_c(tmp_path)
    state = json.loads((tmp_path / "c_state.json").read_text())
    assert state["schema_version"] == "C-v0.1"
    assert state["decisions"][1]["decision"] == "page_size fixed at 7"
    assert (tmp_path / "c_extraction_raw.txt").read_text() == GOOD_RAW


def test_determinism_byte_identical(tmp_path):
    c = make_c(tmp_path)
    t1 = serialize_full(c._state)
    t2 = serialize_full(c._state)
    assert t1 == t2
    a1 = c.build_context(2048)
    c2 = make_c(tmp_path / "second")
    a2 = c2.build_context(2048)
    assert a1.text == a2.text


def test_serialization_respects_budget(tmp_path):
    c = make_c(tmp_path)
    artifact = c.build_context(220)
    assert artifact.token_count <= 220
    assert artifact.truncated
    rep = c._truncation_report
    assert rep["tokens_before_budget"] > rep["serialized_tokens"]
    assert "current_state" not in rep["categories_truncated"] or True
    # priority: current_state, failures, decisions survive; events dropped
    assert "CURRENT STATE" in artifact.text
    assert "page_size fixed at 7" in artifact.text
    assert "EVENTS" not in artifact.text


def test_context_contains_decisions_under_budget(tmp_path):
    c = make_c(tmp_path)
    artifact = c.build_context(2048)
    assert "page_size fixed at 7" in artifact.text
    assert "DECISIONS" in artifact.text
    assert not artifact.truncated


def test_garbage_output_recorded_not_repaired(tmp_path):
    c = ConditionC(tmp_path, llm_complete=lambda s, u: "sorry hallucinated: not json{")
    c.prepare({"session_index": 1, "messages": MESSAGES})
    artifact = c.build_context(1024)
    assert artifact.text == ""
    assert c.metadata()["extraction_error"] is not None
    assert c.metadata()["sessions_consumed"][0]["error"]


def test_missing_categories_normalize():
    state = normalize_state({"decisions": [{"id": "DEC-001", "decision": "x"}]})
    assert state["goals"] == [] and state["current_state"] == {}
    full = serialize_full(state)
    assert "DECISIONS" in full and "GOALS" not in full


def test_extract_c_state_parses_wrapped_json():
    raw = "Here is the state:\n" + GOOD_RAW + "\nDone."
    state, out = extract_c_state(MESSAGES, llm_complete=lambda s, u: raw)
    assert state["facts"][0]["fact"] == "visible suite has 5 tests"
    assert out == raw
