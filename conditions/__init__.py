from conditions.a import ConditionA
from conditions.b import ConditionB
from conditions.base import ContextArtifact, ContinuityCondition
from conditions.c import ConditionC
from conditions.d import ConditionD

CONDITIONS: dict[str, type] = {
    "A": ConditionA,
    "B": ConditionB,
    "C": ConditionC,
    "D": ConditionD,
}

__all__ = [
    "CONDITIONS",
    "ContextArtifact",
    "ContinuityCondition",
    "ConditionA",
    "ConditionB",
    "ConditionC",
    "ConditionD",
]
