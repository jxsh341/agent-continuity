"""Benchmark: evolving_state — apply the latest of a superseding decision chain.

Fact types: exact value ×2 (old 25, new 40), temporal scope (which supersedes).
"""

from __future__ import annotations

from pathlib import Path

BENCHMARK_ID = "evolving_state_v1"

OLD_RATE = 25
NEW_RATE = 40

SEED_FILES = {
    "pytest.ini": "[pytest]\ntestpaths = tests\n",
    "app/__init__.py": "",
    "app/pricing.py": '''"""Pricing rules."""

PENALTY_RATE = 25


def price(base):
    return base * (1 + PENALTY_RATE / 100)
''',
    "tests/test_pricing.py": '''from app.pricing import price, PENALTY_RATE


def test_rate():
    assert PENALTY_RATE == 25


def test_price():
    assert price(100) == 125
''',
}

TASK_S1 = (
    "Review app/pricing.py. Note the policy: PENALTY_RATE was 25 last "
    "quarter; the team has decided to raise it to 40, effective this "
    "session. Do NOT implement the change yet (it's a schedule-constrained"
    " task for the next session). Run the visible tests once to confirm "
    "baseline behavior."
)
TASK_S2 = (
    "Apply the pricing penalty change that was decided in the earlier "
    "session. Exactly what was decided applies. Update tests to match."
)

HIDDEN_TEST = '''"""Injected post-S2."""
import app.pricing as pricing


def test_rate_applied():
    assert pricing.PENALTY_RATE == 40


def test_price():
    assert pricing.price(100) == 140
'''


CRITICAL_FACTS = [
    {"id": "ES-old-value", "label": "25", "type": "exact_value",
     "check": lambda c: "25" in c},
    {"id": "ES-new-value", "label": "40", "type": "exact_value",
     "check": lambda c: "40" in c},
]


def make_seed(root: Path) -> None:
    for rel, text in SEED_FILES.items():
        p = root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text)


def apply_s1_reference(root: Path) -> None:
    # S1 only assesses; nothing changes. Reference state = seed.
    pass


def inject_hidden_tests(root: Path) -> None:
    (root / "tests" / "test_pricing_hidden.py").write_text(HIDDEN_TEST)


def contamination_scan(root: Path) -> bool:
    for p in root.rglob("*"):
        if p.is_file() and p.name == "pricing.py":
            t = p.read_text(errors="ignore")
            return "40" in t
    return False
