"""Benchmark: entity_relationship — preserve a name→attributes mapping decision.

S1: given ledger helpers seeded with entry tuples including per-entry
    days_outstanding values, implement `days_outstanding(account)` helper.

S2: set the billing window rule communicated in S1 (30 days), and expose
    it as the constant BILLING_WINDOW_DAYS in app/ledger.py.
"""

from __future__ import annotations

from pathlib import Path

BENCHMARK_ID = "entity_relationship_v1"

ENTITY = "invoice-service"
WINDOW = 30

SEED_FILES = {
    "pytest.ini": "[pytest]\ntestpaths = tests\n",
    "app/__init__.py": "",
    "app/ledger.py": '''"""Ledger bookkeeping."""

ENTRIES = []


def add_entry(account, amount, days_outstanding=0):
    ENTRIES.append((account, amount, days_outstanding))


def balance(account):
    return sum(amount for acct, amount, _ in ENTRIES if acct == account)
''',
    "tests/test_ledger.py": '''from app.ledger import add_entry, balance


def test_balance():
    add_entry("acct", 500)
    assert balance("acct") == 500
''',
}

TASK_S1 = (
    "Implement a new helper days_outstanding(account) in app/ledger.py that "
    "returns the sum of the days_outstanding stored for the given account's "
    "entries. Write a test for it in tests/test_ledger.py and make the suite "
    "pass.\n\n"
    "Note (shared earlier this week): the billing window for account-level "
    "aging will be 30 days. Also for later: it applies to the "
    "'invoice-service' entity. Do not write either value into the repo."
)
TASK_S2 = (
    "Finalize the accounting rule: add the billing-window constant to "
    "app/ledger.py. Exactly what was decided applies. Do not invent new "
    "values."
)

HIDDEN_TEST = '''"""Injected post-S2."""
import app.ledger as ledger


def test_days_outstanding_helper():
    ledger.add_entry("invoice-service", 500, days_outstanding=7)
    ledger.add_entry("invoice-service", 300, days_outstanding=9)
    assert ledger.days_outstanding("invoice-service") == 16


def test_billing_window_constant_set():
    assert ledger.BILLING_WINDOW_DAYS == 30
'''


CRITICAL_FACTS = [
    {"id": "ER-entity-name", "label": ENTITY, "type": "exact_identifier",
     "check": lambda c: ENTITY in c},
    {"id": "ER-window", "label": "30", "type": "exact_value",
     "check": lambda c: "30" in c},
]


def make_seed(root: Path) -> None:
    for rel, text in SEED_FILES.items():
        p = root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text)


def apply_s1_reference(root: Path) -> None:
    p = root / "app" / "ledger.py"
    p.write_text(p.read_text() + '''

def days_outstanding(account):
    return sum(d for acct, _amt, d in ENTRIES if acct == account)
''')
    t = root / "tests" / "test_ledger.py"
    t.write_text(t.read_text() + '''

def test_days_outstanding_helper():
    add_entry("x", 1, days_outstanding=5)
    from app.ledger import days_outstanding
    assert days_outstanding("x") == 5
''')


def inject_hidden_tests(root: Path) -> None:
    (root / "tests" / "test_ledger_hidden.py").write_text(HIDDEN_TEST)


def contamination_scan(root: Path) -> bool:
    for p in root.rglob("*"):
        if not p.is_file():
            continue
        if "BILLING_WINDOW_DAYS" in p.read_text(errors="ignore"):
            return True
    return False
