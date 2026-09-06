"""Stage 0.4 benchmark repo: a small FastAPI service.

The memory problem is emergent from the engineering workflow:
    Session 1: implement DELETE /items/{id} AND receive design decisions
        for a future endpoint (path, response shape, fixed page size).
        The decisions are explicitly NOT to be written into the repo.
    Session 2: implement /reports/summary per the earlier design.
        Hidden tests (injected post-session) require the agreed
        page size -- information that exists only in the S1
        conversation.

Nothing here mentions the continuity experiment.
"""

from __future__ import annotations
from pathlib import Path

BENCHMARK_ID = "fastapi_shopapi_v1"

# Critical facts, annotated by required fidelity (see BENCHMARK_SPEC_v1.md).
CRITICAL_FACTS = [
    {"id": "CF-reports-path", "label": "/reports/summary",
     "type": "exact_identifier", "check": lambda ctx: "/reports/summary" in ctx},
    {"id": "CF-page-size", "label": "page_size=7", "type": "exact_value",
     "check": lambda ctx: bool(__import__("re").search(
         r"page[_ ]size['\"\s:=]*7\b", ctx, __import__("re").I))},
    {"id": "CF-reports-shape", "label": "'reports' response key",
     "type": "structural",
     "check": lambda ctx: "'reports'" in ctx or '"reports"' in ctx},
    {"id": "CF-defer-now", "label": "deferred to next session",
     "type": "negative_instruction", "check": lambda ctx: True},
]


def apply_oracle(root: Path) -> None:
    addon = '''

@app.get("/reports/summary")
def reports_summary():
    counts = {}
    for i in ITEMS:
        counts[i["category"]] = counts.get(i["category"], 0) + 1
    return {
        "reports": [{"category": c, "count": n} for c, n in counts.items()],
        "page_size": 7,
    }
'''
    with open(root / "app" / "main.py", "a") as f:
        f.write(addon)


# The session-1-only decision values (hidden test asserts these).
REPORTS_PATH = "/reports/summary"
REPORTS_PAGE_SIZE = 7

SEED_FILES: dict[str, str] = {
    "pytest.ini": "[pytest]\ntestpaths = tests\n",
    "app/__init__.py": "",
    "app/main.py": '''"""shopapi: minimal item catalog service."""

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

app = FastAPI(title="shopapi")

ITEMS = [
    {"id": 1, "name": "widget", "category": "tools"},
    {"id": 2, "name": "gear", "category": "tools"},
    {"id": 3, "name": "lamp", "category": "home"},
    {"id": 4, "name": "desk", "category": "home"},
    {"id": 5, "name": "cable", "category": "electronics"},
    {"id": 6, "name": "charger", "category": "electronics"},
    {"id": 7, "name": "mug", "category": "kitchen"},
    {"id": 8, "name": "kettle", "category": "kitchen"},
    {"id": 9, "name": "pan", "category": "kitchen"},
]


class ItemOut(BaseModel):
    id: int
    name: str
    category: str


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/items", response_model=list[ItemOut])
def list_items(category: str | None = None):
    if category is None:
        return ITEMS
    return [i for i in ITEMS if i["category"] == category]
''',
    "tests/test_items.py": '''from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health():
    assert client.get("/health").json() == {"status": "ok"}


def test_list_items_all():
    items = client.get("/items").json()
    assert len(items) == 9


def test_list_items_filter():
    items = client.get("/items", params={"category": "kitchen"}).json()
    assert {i["name"] for i in items} == {"mug", "kettle", "pan"}
''',
    "README.md": (
        "shopapi: minimal FastAPI item catalog.\n\n"
        "Conventions: all endpoints live in app/main.py; response models "
        "via pydantic; tests in tests/ use fastapi.testclient.TestClient.\n"
    ),
}

TASK_S1 = (
    "Implement the DELETE /items/{item_id} endpoint in app/main.py, "
    "following the existing endpoint style: return 404 when the item does "
    "not exist and an empty 204-style success otherwise (returning the "
    "deleted item is also acceptable if that matches the codebase "
    "conventions you find). Extend tests/test_items.py with tests for the "
    "new endpoint and make the full visible suite pass.\n\n"
    "Separately, the team has finalized the design for a future reports "
    "endpoint that will be implemented in the NEXT working session:\n"
    f"  - Path: {REPORTS_PATH}\n"
    "  - Behavior: aggregate the item counts grouped by category\n"
    "  - Response JSON object with keys: 'reports' (list of "
    "{'category': str, 'count': int}) and 'page_size' (an agreed fixed "
    "value)\n"
    "  - The agreed fixed page size is 7\n"
    "Do NOT implement the reports endpoint now, and do NOT write the page "
    "size value (or any part of the reports design) into the repository; "
    "it will be provided at implementation time."
)

TASK_S2 = (
    "Implement the reports endpoint exactly as designed in the earlier "
    "session: the path, aggregation behavior, response shape, and the "
    "agreed fixed page size were all decided then. Do not invent new "
    "values for decisions that were already made. Keep the existing test "
    "suite green."
)

HIDDEN_TEST = '''"""Injected by the experiment harness after the agent finishes.

Asserts the design decision that was only communicated in session 1.
"""
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_reports_summary_page_size():
    r = client.get("__REPORTS_PATH__")
    assert r.status_code == 200
    body = r.json()
    assert body.get("page_size") == __PAGE_SIZE__
    assert isinstance(body.get("reports"), list)


def test_reports_summary_aggregation():
    r = client.get("__REPORTS_PATH__")
    body = r.json()
    by_cat = {row["category"]: row["count"] for row in body["reports"]}
    assert by_cat.get("kitchen") == 3
    assert by_cat.get("home") == 2
'''.replace("__REPORTS_PATH__", REPORTS_PATH).replace("__PAGE_SIZE__", str(REPORTS_PAGE_SIZE))


def make_seed(root: Path) -> None:
    for rel, content in SEED_FILES.items():
        p = root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content)


def inject_hidden_tests(root: Path) -> None:
    (root / "tests" / "test_reports_hidden.py").write_text(HIDDEN_TEST)


def contamination_scan(root: Path) -> bool:
    """True if the page-size decision leaked into the repo."""
    for p in root.rglob("*"):
        if p.is_file() and "page_size" in p.read_text(encoding="utf-8", errors="ignore"):
            return True
    return False


def scrub_session_notes(root: Path) -> list[str]:
    """Remove agent-authored memory surfaces at the session boundary.

    OpenHands' default system prompt instructs agents to use AGENTS.md
    as persistent memory. Allowing that file to ride along with the
    workspace would give every condition free cross-session memory and
    break the causal structure: in this experiment, ONLY the condition
    may carry information across sessions.

    Returns the list of removed relative paths (recorded in results).
    """
    removed: list[str] = []
    for rel in ("AGENTS.md", ".agents.md"):
        p = root / rel
        if p.exists():
            p.unlink()
            removed.append(rel)
    return removed
