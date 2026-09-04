from dataclasses import dataclass


@dataclass(frozen=True)
class Task:
    task_id: str
    session: int
    prompt: str
    targeted_tests: tuple[str, ...] = ()
    regression_tests: tuple[str, ...] = ()


# Placeholder until §8.1 task construction is committed blind to C's results.
STAGE0_TASKS = (
    Task("S1", 1, "STAGE0_PLACEHOLDER"),
    Task("S2", 2, "STAGE0_PLACEHOLDER"),
)
