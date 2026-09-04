"""Result type returned by the coding-agent adapter.

Token accounting is done HERE, outside OpenHands, by reading
`llm.metrics` after the run. The experiment layer records these fields.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class AgentSessionResult:
    task: str
    workspace: str
    initial_context: str

    # Transcript: serialized SDK events (JSON-able dicts).
    events: list[dict] = field(default_factory=list)

    # Simple role/content transcript — the canonical input the
    # condition layer consumes via SessionRecord["messages"].
    messages: list[dict] = field(default_factory=list)

    # Token accounting (from llm.metrics, post-run).
    llm_metrics: dict = field(default_factory=dict)

    # Reproducibility: effective agent framework identity.
    agent_framework: str = "openhands-software-agent-sdk"
    agent_framework_commit: str = ""
    experiment_metadata: dict = field(default_factory=dict)

    error: str | None = None
