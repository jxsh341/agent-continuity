"""Benchmark v1.2: configuration/infrastructure task.

Memory-critical design: S1 builds a layered config loader; the deploy
decision (env var name, value, config key) is communicated for the NEXT
session and must not enter the repo.
"""

from __future__ import annotations

from pathlib import Path

BENCHMARK_ID = "config_env_v1"

ENV_VAR = "SHOPAPI_RATE_LIMIT_RPS"
RATE_LIMIT = "42"
CONFIG_KEY = "rate_limit_rps"

SEED_FILES: dict[str, str] = {
    "pytest.ini": "[pytest]\ntestpaths = tests\n",
    "app/__init__.py": "",
    "app/config.py": '''"""config: layered configuration for shopapi."""

from pathlib import Path

import yaml

DEFAULTS_PATH = Path(__file__).parent.parent / "config" / "defaults.yaml"


def load_config() -> dict:
    """Load the base config. Session 1 extends this function."""
    return yaml.safe_load(DEFAULTS_PATH.read_text())
''',
    "config/defaults.yaml": (
        "service: shopapi\n"
        "retries: 3\n"
        "timeout_ms: 500\n"
    ),
    "tests/test_config.py": '''from app.config import load_config


def test_defaults_loaded():
    cfg = load_config()
    assert cfg["service"] == "shopapi"
    assert cfg["retries"] == 3
    assert cfg["timeout_ms"] == 500
''',
    "README.md": (
        "Conventions: config keys are snake_case strings stored in "
        "config/defaults.yaml; app/config.py exposes load_config() -> dict.\n"
    ),
}

TASK_S1 = (
    "Extend app/config.py so load_config() additionally supports overriding "
    "any key with an environment variable of the same name in UPPER_SNAKE "
    "(e.g. RETRIES overrides retries, parsed as int when the default is an "
    "int). Add tests and make the full visible suite pass.\n\n"
    "Separately, the deploy decision for the next session has been made: the "
    "rate limit will be exposed via environment variable "
    f"`{ENV_VAR}` deciding config key `{CONFIG_KEY}`, and its intended value "
    f"is `{RATE_LIMIT}`. Do NOT add this mapping now, and do NOT write the "
    "variable name or value into the repository; it will be provided at "
    "implementation time."
)

TASK_S2 = (
    "Implement the rate-limit configuration exactly as decided in the "
    "earlier session: the environment variable name, the config key it "
    "feeds, and the intended value were all decided then. The loader must "
    "convert the value to int if the key is introduced new (no existing "
    "default). Do not invent new names or values. Keep the existing test "
    "suite green."
)

HIDDEN_TEST = '''"""Injected by the experiment harness after the agent finishes."""

import os

from app.config import load_config


def test_env_var_feeds_config(monkeypatch):
    monkeypatch.setenv("__ENV__", "__VAL__")
    cfg = load_config()
    assert cfg["__KEY__"] == __VAL_INT__


def test_default_absent_without_env(monkeypatch):
    monkeypatch.delenv("__ENV__", raising=False)
    cfg = load_config()
    assert "__KEY__" not in cfg
'''.replace("__ENV__", ENV_VAR).replace("__KEY__", CONFIG_KEY).replace("__VAL_INT__", RATE_LIMIT).replace("__VAL__", RATE_LIMIT)

CRITICAL_FACTS = [
    {"id": "CF-env-var", "label": ENV_VAR, "type": "exact_identifier",
     "check": lambda ctx: ENV_VAR in ctx},
    {"id": "CF-config-key", "label": CONFIG_KEY, "type": "exact_identifier",
     "check": lambda ctx: CONFIG_KEY in ctx},
    {"id": "CF-rate-value", "label": RATE_LIMIT, "type": "exact_value",
     "check": lambda ctx: bool(__import__("re").search(r"\b42\b", ctx))},
    {"id": "CF-defer-now", "label": "deferred to next session",
     "type": "negative_instruction", "check": lambda ctx: True},
]

_ORACLE = '''

_ENV_KEY_MAP = {"SHOPAPI_RATE_LIMIT_RPS": "rate_limit_rps"}


def load_config() -> dict:
    import os

    cfg = yaml.safe_load(DEFAULTS_PATH.read_text())
    for key, val in os.environ.items():
        target = _ENV_KEY_MAP.get(key, key.lower())
        if target in cfg or target in _ENV_KEY_MAP.values():
            if isinstance(cfg.get(target), int):
                val = int(val)
            elif target == "rate_limit_rps":
                val = int(val)
            cfg[target] = val
    return cfg
'''


def make_seed(root: Path) -> None:
    for rel, content in SEED_FILES.items():
        p = root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content)


def inject_hidden_tests(root: Path) -> None:
    (root / "tests" / "test_config_hidden.py").write_text(HIDDEN_TEST)


def contamination_scan(root: Path) -> bool:
    for p in root.rglob("*"):
        if p.is_file() and ENV_VAR in p.read_text(encoding="utf-8", errors="ignore"):
            return True
    return False


def apply_oracle(root: Path) -> None:
    with open(root / "app" / "config.py", "a") as f:
        f.write(_ORACLE)


_S1_REFERENCE = '''

def load_config() -> dict:
    """S1 reference: generic env override layer. The rate-limit mapping
    (SHOPAPI_RATE_LIMIT_RPS -> rate_limit_rps) is the S2, fact-dependent
    work and is intentionally absent here."""
    import os

    cfg = yaml.safe_load(DEFAULTS_PATH.read_text())
    for key, val in os.environ.items():
        target = key.lower()
        if target in cfg:
            if isinstance(cfg[target], int):
                cfg[target] = int(val)
            else:
                cfg[target] = val
    return cfg
'''


def apply_s1_reference(root: Path) -> None:
    """Diagnostic only (C-oracle ablation): correct S1 = generic env
    override. Leaves the SHOPAPI_RATE_LIMIT_RPS mapping to S2."""
    with open(root / "app" / "config.py", "a") as f:
        f.write(_S1_REFERENCE)
