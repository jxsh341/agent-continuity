"""Benchmark: cache_profile — (facts: exact numeric value, negative instruction, structural).

S1: implement a basic cache; hidden S1 design decision: TTL must be 300 s
and eviction must happen only every 60 s (per a previous incident with an
overly short interval). S2: finalize the eviction policy using those exact
settings.
"""

from __future__ import annotations

from pathlib import Path

BENCHMARK_ID = "cache_profile_v1"

CACHE_TTL = 300
EVICT_EVERY = 60

SEED_FILES: dict[str, str] = {
    "pytest.ini": "[pytest]\ntestpaths = tests\n",
    "app/__init__.py": "",
    "app/cache.py": '''"""Simple in-process cache."""

import time


def now():
    return time.time()


class Cache:
    def __init__(self):
        self.store = {}

    def set(self, key, value):
        self.store[key] = (value, None if False else now())

    def get(self, key):
        return self.store.get(key, (None, None))[0]
''',
    "tests/test_cache.py": '''from app.cache import Cache


def test_set_get():
    c = Cache()
    c.set("k", 5)
    assert c.get("k") == 5
''',
}

TASK_S1 = (
    "Extend app/cache.py to make Cache time-aware: Cache.get() should return "
    "None if the entry's timestamp is older than `ttl`, and Cache#set should "
    "record the set-time. Do not implement expiry threads/timers yet — "
    "eviction policy will be finalized later. Run tests."
)
TASK_S1 += "\n\nAlso note the team's policy: cache TTL will be finalized next session; the strict value is 300, and eviction sweeps run at 60-second intervals. DO NOT encode either number into the repo now."

TASK_S2 = (
    "Implement the previously decided eviction scheduling: read the TTL from "
    "a constant and the sweep interval from another constant exactly as "
    "decided. No new values."
)

HIDDEN_TEST = '''"""Injected post-run."""
import importlib, time
import app.cache as cache_mod


def test_ttl_value():
    assert hasattr(cache_mod, "CACHE_TTL")
    assert cache_mod.CACHE_TTL == 300


def test_evict_interval():
    assert hasattr(cache_mod, "EVICT_EVERY")
    assert cache_mod.EVICT_EVERY == 60
'''

CRITICAL_FACTS = [
    {"id": "CP-ttl", "label": "300", "type": "exact_value",
     "check": lambda x: "300" in x},
    {"id": "CP-evict", "label": "60", "type": "exact_value",
     "check": lambda x: "60" in x},
]


def make_seed(root: Path) -> None:
    for rel, text in SEED_FILES.items():
        p = root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text)


def inject_hidden_tests(root: Path) -> None:
    (root / "tests" / "test_cache_hidden.py").write_text(HIDDEN_TEST)


def contamination_scan(root: Path) -> bool:
    return any(
        "300" in p.read_text(errors="ignore") or "sweep" in p.read_text(errors="ignore")
        for p in root.rglob("*") if p.is_file() and p.suffix == ".py" and p.name != "test_cache.py"
    )


def apply_s1_reference(root: Path) -> None:
    add = '''


class TimedCache(Cache):
    pass  # TTL support intentionally deferred to next session.
'''
    (root / "app" / "cache.py").write_text(
        open(root / "app" / "cache.py").read() + add
    )
