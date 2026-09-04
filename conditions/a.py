"""Condition A: no memory. Negative control.

prepare() deliberately discards everything; build_context() always
returns an empty artifact.
"""

from __future__ import annotations

from conditions.base import ContextArtifact, ContinuityCondition, SessionRecord


class ConditionA(ContinuityCondition):
    name = "A"

    def prepare(self, previous_session: SessionRecord) -> None:
        return None

    def build_context(self, budget_tokens: int, task: str | None = None) -> ContextArtifact:
        return ContextArtifact(
            text="",
            token_count=0,
            budget_tokens=budget_tokens,
            truncated=False,
            condition=self.name,
        )

    def metadata(self) -> dict:
        return {"condition": self.name, "detail": "no memory survives sessions"}
