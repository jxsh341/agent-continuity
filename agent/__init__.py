"""Agent layer: thin adapter around the external OpenHands Software Agent SDK.

This package owns ONLY: model configuration, the frozen session-message
construction, and the OpenHands adapter. It does NOT own memory or
experiment logic (those live in `continuity/` and `conditions/`).
"""

from agent.config import ModelConfig
from agent.models import AgentSessionResult
from agent.openhands_adapter import CodingAgent, OpenHandsCodingAgent

__all__ = [
    "ModelConfig",
    "AgentSessionResult",
    "CodingAgent",
    "OpenHandsCodingAgent",
]
