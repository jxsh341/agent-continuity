"""Frozen condition interface (Milestone 0.3).

Every condition implements the same contract. The experiment runner
(and therefore the agent adapter) cannot tell conditions apart: it only
receives a ContextArtifact. This separation is what keeps the A/B/C/D
comparison unbiased.

    previous SessionRecord
            │  prepare()
            ▼
      condition state
            │  build_context(budget)
            ▼
      ContextArtifact ──► fresh OpenHands session
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass, field
from typing import Any

# What a finished session hands to the condition layer.
# `messages` is a simple [{"role": ..., "content": ...}] transcript
# (harvested from SDK events by the adapter); `events` stays on disk.
SessionRecord = dict[str, Any]


@dataclass(frozen=True)
class ContextArtifact:
    """The ONLY thing that may cross the session boundary."""

    text: str
    token_count: int
    budget_tokens: int
    truncated: bool
    condition: str
    provenance: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)


class ContinuityCondition(ABC):
    name: str

    @abstractmethod
    def prepare(self, previous_session: SessionRecord) -> None:
        """Consume a finished session. Called by the runner after each
        session completes, before the next session's build_context."""

    @abstractmethod
    def build_context(
        self, budget_tokens: int, task: str | None = None
    ) -> ContextArtifact:
        """Produce the continuation context for the NEXT session,
        already within the token budget. `task` is the upcoming
        session's task text, available for retrieval-conditioned
        conditions (e.g. B); A and D ignore it."""

    @abstractmethod
    def metadata(self) -> dict[str, Any]:
        """Condition-specific, JSON-serializable reproducibility info."""
