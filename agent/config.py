"""Model configuration for the coding agent.

Environment variables (same convention as the OpenHands SDK examples):
    LLM_MODEL, LLM_API_KEY, LLM_BASE_URL
"""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class ModelConfig:
    model: str = "meta/muse-glimmer-30b"
    api_key: str | None = None
    base_url: str | None = None
    # Hard cap on agent loop iterations per session. Protects run time
    # against dithering models; part of the frozen harness config.
    max_iterations: int = 80

    @classmethod
    def from_env(cls) -> "ModelConfig":
        return cls(
            model=os.getenv("LLM_MODEL", cls.model),
            api_key=os.getenv("LLM_API_KEY") or None,
            base_url=os.getenv("LLM_BASE_URL") or None,
        )
