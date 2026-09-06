"""Condition C: structured continuity state (the research contribution).

Pipeline (v0.1, deliberately no retrieval machinery):
    prepare():       transcript -> frozen extractor (shared model/prompt)
                     -> validated C-v0.1 state -> artifacts on disk:
                        c_extraction_raw.txt, c_state.json
    build_context(): state -> deterministic serializer (frozen section
                     order + priority truncation) -> budget artifact.
                     Serialization saved as c_context.txt.
    metadata():      full provenance incl. truncation report.

The state the agent sees contains NO mention of the experiment, memory,
conditions, or continuity. It is framed only as "Previous session state".

Invariants recorded (not enforced by repair): extraction garbage ->
error recorded and empty artifact; nothing silently fixed.
"""

from __future__ import annotations

import json
from pathlib import Path

from conditions.base import ContextArtifact, ContinuityCondition, SessionRecord
from continuity.tokens import count_tokens
from extractors.c_extractor import (
    ExtractionError,
    ExtractionTransportError,
    extract_c_state,
    extractor_identity,
)
from serialization.c_serializer import serialize_full, serialize_within_budget


class ConditionC(ContinuityCondition):
    name = "C"

    def __init__(
        self,
        store_root: Path | None = None,
        llm_complete=None,  # offline tests inject a fake
    ):
        self._root = Path(store_root) if store_root else None
        if self._root:
            self._root.mkdir(parents=True, exist_ok=True)
        self._llm_complete = llm_complete
        self._state: dict | None = None
        self._raw: str | None = None
        self._error: str | None = None
        self._sessions: list[dict] = []
        self._truncation_report: dict = {}

    def prepare(self, previous_session: SessionRecord) -> None:
        messages = previous_session.get("messages") or []
        idx = previous_session.get("session_index", 0)
        if not messages:
            return
        try:
            state, raw = extract_c_state(messages, llm_complete=self._llm_complete)
        except ExtractionTransportError as e:
            # AMD-001: infra failure must propagate so the runner records
            # it explicitly instead of counting it as a C outcome.
            self._sessions.append(
                {"session_index": idx, "infrastructure_failure": str(e)}
            )
            self._write("c_extraction_raw.txt", "")
            raise
        except ExtractionError as e:
            self._error = str(e)
            self._raw = None
            self._sessions.append({"session_index": idx, "error": self._error})
            self._write("c_extraction_raw.txt", "")
            return
        self._state, self._raw = state, raw
        self._error = None
        self._sessions.append({"session_index": idx, "ok": True})
        self._write("c_extraction_raw.txt", raw)
        self._write("c_state.json", json.dumps(state, indent=2))

    def build_context(self, budget_tokens: int, task: str | None = None) -> ContextArtifact:
        if self._state is None:
            return ContextArtifact(
                text="", token_count=0, budget_tokens=budget_tokens,
                truncated=False, condition=self.name,
                provenance={"extraction_error": self._error},
            )
        text, report = serialize_within_budget(self._state, budget_tokens)
        self._truncation_report = report
        self._write("c_context.txt", text)
        self._write("c_truncation_report.json", json.dumps(report, indent=2))
        return ContextArtifact(
            text=text,
            token_count=count_tokens(text),
            budget_tokens=budget_tokens,
            truncated=report["truncated"],
            condition=self.name,
            provenance={
                "schema_version": "C-v0.1",
                "extractor": extractor_identity(),
                **report,
            },
        )

    def metadata(self) -> dict:
        return {
            "condition": self.name,
            "schema_version": "C-v0.1",
            "extractor": extractor_identity(),
            "serialization": "deterministic serializer (frozen order)",
            "sessions_consumed": self._sessions,
            "extraction_error": self._error,
            "truncation_report": self._truncation_report,
        }

    def _write(self, name: str, content: str) -> None:
        if self._root:
            (self._root / name).write_text(content, encoding="utf-8")


# Convenience for tests/inspection: serialize helper is importable too.
__all__ = ["ConditionC", "serialize_full", "serialize_within_budget"]
