from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class RunConfig:
    provider: str = "stub"
    model: str = "stub-v0"
    temperature: float = 0.0
    top_p: float = 1.0
    max_tokens: int = 4096
    context_budget: int = 4096
    condition: str = "A"
    session_count: int = 2
    run_seed: int = 0
    benchmark_version: str = "0.1.0"


@dataclass
class SessionResult:
    run_id: str
    session_index: int
    task_success: bool
    tokens_in: int = 0
    tokens_out: int = 0
    latency_seconds: float = 0.0
    checks: dict[str, Any] = field(default_factory=dict)
    transcript_path: str | None = None


@dataclass
class Workspace:
    root: Path

    def reset_from_seed(self, seed_repo: Path) -> None:
        import shutil
        if self.root.exists():
            shutil.rmtree(self.root)
        shutil.copytree(seed_repo, self.root)
