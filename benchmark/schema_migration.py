"""Benchmark v1.1: schema migration task (stdlib sqlite3 only).

Memory-critical design: S1 implements a migration runner and is told the
design of the NEXT migration (filename, table, columns) without writing
it into the repo. S2 must create that migration exactly.

Critical facts are annotated by required fidelity (see BENCHMARK_SPEC_v1.md).
"""

from __future__ import annotations

import re
from pathlib import Path

BENCHMARK_ID = "schema_migration_v1"

NEXT_MIGRATION = "003_add_audit_log.sql"
TABLE = "audit_log"
COLUMNS = ("id", "event", "created_at")

SEED_FILES: dict[str, str] = {
    "pytest.ini": "[pytest]\ntestpaths = tests\n",
    "app/__init__.py": "",
    "app/db.py": '''"""db: toy migration runner over an sqlite database."""

import sqlite3
from pathlib import Path

MIGRATIONS_DIR = Path(__file__).parent.parent / "migrations"


def connect(db_path):
    return sqlite3.connect(db_path)


def tables(conn):
    rows = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'"
    ).fetchall()
    return sorted(r[0] for r in rows)


def applied_migrations(conn):
    if "migration_log" not in tables(conn):
        return []
    rows = conn.execute("SELECT name FROM migration_log ORDER BY name").fetchall()
    return [r[0] for r in rows]
''',
    "migrations/001_init.sql": (
        "CREATE TABLE items (id INTEGER PRIMARY KEY, name TEXT);\n"
    ),
    "migrations/002_add_category.sql": (
        "ALTER TABLE items ADD COLUMN category TEXT;\n"
    ),
    "tests/test_db.py": '''import sqlite3

from app.db import connect, tables, applied_migrations


def test_schema_starts_empty(tmp_path):
    conn = connect(tmp_path / "t.db")
    assert tables(conn) == []


def test_no_migrations_applied(tmp_path):
    conn = connect(tmp_path / "t.db")
    assert applied_migrations(conn) == []
''',
    "README.md": (
        "Migration conventions: SQL files in migrations/, named "
        "NNN_snake_case_slug.sql (numbers assigned sequentially, starting at "
        "001), applied in numeric order. Every file that gets applied is "
        "recorded in a `migration_log(name)` table.\n"
    ),
}

TASK_S1 = (
    "Implement the migration runner in this project: an "
    "`apply_pending(conn)` function in app/db.py that reads the SQL files "
    "in migrations/, applies not-yet-applied ones in numeric order inside "
    "transactions, and records each applied migration name in a "
    "`migration_log(name)` table. Extend tests/test_db.py so the existing "
    "two migrations (001_init.sql, 002_add_category.sql) are covered, and "
    "make the full visible suite pass.\n\n"
    "Separately, the design for the NEXT migration has been finalized for a "
    f"future session: filename `{NEXT_MIGRATION}`; it creates a table "
    f"`{TABLE}` with columns "
    f"{', '.join(COLUMNS)} (id INTEGER PRIMARY KEY, event TEXT, created_at "
    "INTEGER). Do NOT create that migration now, and do NOT write any part "
    "of this design into the repository; it will be provided again at "
    "implementation time."
)

TASK_S2 = (
    "Create the design-approved migration exactly as decided in the earlier "
    "session (filename, table, columns) and make sure the migration runner "
    "applies it. Do not invent new values for decisions that were already "
    "made. Keep the existing test suite green."
)

HIDDEN_TEST = '''"""Injected by the experiment harness after the agent finishes."""
import sqlite3
from pathlib import Path

from app.db import connect, apply_pending, tables, applied_migrations


def test_migration_003_applied(tmp_path):
    conn = connect(tmp_path / "t.db")
    apply_pending(conn)
    assert "__TABLE__" in tables(conn)
    cols = [r[1] for r in conn.execute("PRAGMA table_info(__TABLE__)")]
    assert cols == ["id", "event", "created_at"]


def test_migration_recorded(tmp_path):
    conn = connect(tmp_path / "t.db")
    apply_pending(conn)
    assert "__NAME__" in applied_migrations(conn)


def test_migration_file_exact():
    files = [p.name for p in Path("migrations").glob("*.sql")]
    assert "__NAME__" in files
'''.replace("__TABLE__", TABLE).replace("__NAME__", NEXT_MIGRATION)

# Critical facts, annotated by required fidelity (see BENCHMARK_SPEC_v1.md).
CRITICAL_FACTS = [
    {"id": "CF-migration-filename", "label": NEXT_MIGRATION,
     "type": "exact_identifier",
     "check": lambda ctx: NEXT_MIGRATION in ctx},
    {"id": "CF-table-name", "label": TABLE, "type": "exact_identifier",
     "check": lambda ctx: TABLE in ctx},
    {"id": "CF-columns", "label": "id,event,created_at", "type": "structural",
     "check": lambda ctx: bool(
         __import__("re").search(r"\bid\b", ctx)
         and __import__("re").search(r"\bevent\b", ctx)
         and "created_at" in ctx
     )},
    {"id": "CF-defer-now", "label": "deferred to next session",
     "type": "negative_instruction", "check": lambda ctx: True},
]


def make_seed(root: Path) -> None:
    for rel, content in SEED_FILES.items():
        p = root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content)


def inject_hidden_tests(root: Path) -> None:
    (root / "tests" / "test_migration_hidden.py").write_text(HIDDEN_TEST)


def contamination_scan(root: Path) -> bool:
    for p in root.rglob("*"):
        if p.is_file() and TABLE in p.read_text(encoding="utf-8", errors="ignore"):
            return True
    return False


ORACLE_FILES: dict[str, str] = {
    "app/db.py": None,  # appended below
    "migrations/003_add_audit_log.sql": (
        "CREATE TABLE audit_log (\n"
        "    id INTEGER PRIMARY KEY,\n"
        "    event TEXT,\n"
        "    created_at INTEGER\n"
        ");\n"
    ),
}

_ORACLE_DB_APPEND = '''

def apply_pending(conn):
    conn.execute(
        "CREATE TABLE IF NOT EXISTS migration_log (name TEXT PRIMARY KEY)"
    )
    done = set(applied_migrations(conn))
    for path in sorted(MIGRATIONS_DIR.glob("*.sql")):
        if path.name in done:
            continue
        conn.executescript(path.read_text())
        conn.execute("INSERT INTO migration_log (name) VALUES (?)",
                     (path.name,))
    conn.commit()
'''


def apply_oracle(root: Path) -> None:
    """Reference implementation for offline validation only."""
    with open(root / "app" / "db.py", "a") as f:
        f.write(_ORACLE_DB_APPEND)
    (root / "migrations" / NEXT_MIGRATION).write_text(
        ORACLE_FILES["migrations/003_add_audit_log.sql"]
    )
