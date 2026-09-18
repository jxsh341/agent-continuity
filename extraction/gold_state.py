"""Gold-state extractor for Phase 2 (reliable-extraction arm).

Builds a C-v0.1 state directly from the frozen benchmark CRITICAL_FACTS.
This is an EXPERIMENTAL INSTRUMENT, not the production extractor: it removes
the stochastic extraction confound so the structured representation itself can
be evaluated. The gold state passes through the FROZEN C schema and serializer
exactly like a real extraction would.

No LLM calls. No changes to C-v0.1, serializer, benchmarks, or Stage 1A data.
"""

from __future__ import annotations

from extraction import metrics

# Canonical C-v0.1 state per benchmark. Facts are expressed verbatim so the
# frozen serializer renders them into the S2 context text containing every
# critical fact exactly.
GOLD_STATE: dict[str, dict] = {
    "fastapi": {
        "schema_version": "C-v0.1",
        "goals": [{"id": "G-001", "description": "implement the reports endpoint exactly per design"}],
        "tasks": [{"id": "TASK-001", "description": "add /reports/summary endpoint", "status": "pending", "files": ["app/main.py"]}],
        "decisions": [
            {"id": "DEC-001", "decision": "reports endpoint path is /reports/summary", "reason": "team design", "status": "active"},
            {"id": "DEC-002", "decision": "response shape is {'reports': [{'category': str, 'count': int}], 'page_size': 7}", "reason": "team design", "status": "active"},
        ],
        "entities": [],
        "facts": [
            {"id": "F-001", "fact": "page_size is fixed at 7"},
            {"id": "F-002", "fact": "aggregation groups item counts by category"},
        ],
        "events": [],
        "failures": [],
        "dependencies": [{"id": "DEP-001", "description": "reuse existing ITEMS list"}],
        "current_state": {"active_work": "reports endpoint pending", "tests_status": "visible suite green"},
    },
    "schema_migration": {
        "schema_version": "C-v0.1",
        "goals": [{"id": "G-001", "description": "create the design-approved migration exactly"}],
        "tasks": [{"id": "TASK-001", "description": "add migration 003_add_audit_log.sql", "status": "pending", "files": ["migrations/003_add_audit_log.sql"]}],
        "decisions": [
            {"id": "DEC-001", "decision": "next migration filename is 003_add_audit_log.sql", "reason": "team design", "status": "active"},
            {"id": "DEC-002", "decision": "migration creates table audit_log with columns id (INTEGER PRIMARY KEY), event (TEXT), created_at (INTEGER)", "reason": "team design", "status": "active"},
        ],
        "entities": [{"id": "E-001", "name": "audit_log", "type": "table", "description": "new migration target"}],
        "facts": [
            {"id": "F-001", "fact": "migration filename is 003_add_audit_log.sql"},
            {"id": "F-002", "fact": "columns are id, event, created_at"},
        ],
        "events": [],
        "failures": [],
        "dependencies": [{"id": "DEP-001", "description": "applied via existing apply_pending runner"}],
        "current_state": {"active_work": "migration 003 pending", "tests_status": "visible suite green"},
    },
    "config_env": {
        "schema_version": "C-v0.1",
        "goals": [{"id": "G-001", "description": "wire the rate-limit env mapping exactly per deploy decision"}],
        "tasks": [{"id": "TASK-001", "description": "add SHOPAPI_RATE_LIMIT_RPS mapping", "status": "pending", "files": ["app/config.py"]}],
        "decisions": [
            {"id": "DEC-001", "decision": "environment variable SHOPAPI_RATE_LIMIT_RPS feeds config key rate_limit_rps with intended value 42", "reason": "deploy decision", "status": "active"},
        ],
        "entities": [],
        "facts": [
            {"id": "F-001", "fact": "env var is SHOPAPI_RATE_LIMIT_RPS"},
            {"id": "F-002", "fact": "config key is rate_limit_rps"},
            {"id": "F-003", "fact": "intended value is 42"},
        ],
        "events": [],
        "failures": [],
        "dependencies": [{"id": "DEP-001", "description": "loader already supports env override"}],
        "current_state": {"active_work": "rate-limit mapping pending", "tests_status": "visible suite green"},
    },
    "cache_policy": {
        "schema_version": "C-v0.1",
        "goals": [{"id": "G-001", "description": "finalize cache eviction policy exactly as decided"}],
        "tasks": [{"id": "TASK-001", "description": "expose EVICT_EVERY and cache TTL constants", "status": "pending", "files": ["app/cache.py"]}],
        "decisions": [
            {"id": "DEC-001", "decision": "cache TTL is 300 seconds; eviction sweep runs every 60 seconds", "reason": "capacity decision", "status": "active"},
        ],
        "entities": [],
        "facts": [
            {"id": "F-001", "fact": "cache TTL is 300"},
            {"id": "F-002", "fact": "eviction interval is 60"},
        ],
        "events": [],
        "failures": [],
        "dependencies": [{"id": "DEP-001", "description": "existing Cache class"}],
        "current_state": {"active_work": "eviction policy pending", "tests_status": "visible suite green"},
    },
    "entity_relationship": {
        "schema_version": "C-v0.1",
        "goals": [{"id": "G-001", "description": "expose billing window decided earlier"}],
        "tasks": [{"id": "TASK-001", "description": "add BILLING_WINDOW_DAYS constant", "status": "pending", "files": ["app/ledger.py"]}],
        "decisions": [
            {"id": "DEC-001", "decision": "billing window is 30 days for invoice-service", "reason": "accounting decision", "status": "active"},
        ],
        "entities": [
            {"id": "E-001", "name": "invoice-service", "type": "account", "description": "ledger entity"},
        ],
        "facts": [
            {"id": "F-001", "fact": "billing window is 30"},
            {"id": "F-002", "fact": "the affected entity is invoice-service"},
        ],
        "events": [],
        "failures": [],
        "dependencies": [{"id": "DEP-001", "description": "ENRIES has per-entry days_outstanding"}],
        "current_state": {"active_work": "billing-window constant pending", "tests_status": "visible suite green"},
    },
    "evolving_state": {
        "schema_version": "C-v0.1",
        "goals": [{"id": "G-001", "description": "apply the policy rate change exactly as decided"}],
        "tasks": [{"id": "TASK-001", "description": "raise PENALTY_RATE as decided", "status": "pending", "files": ["app/pricing.py", "tests/test_pricing.py"]}],
        "decisions": [
            {"id": "DEC-001", "decision": "PENALTY_RATE changes from 25 to 40", "reason": "pricing policy decision", "status": "active"},
        ],
        "entities": [],
        "facts": [
            {"id": "F-001", "fact": "old rate was 25"},
            {"id": "F-002", "fact": "new rate is 40"},
        ],
        "events": [],
        "failures": [],
        "dependencies": [],
        "current_state": {"active_work": "rate change pending", "tests_status": "visible suite green"},
    },
}


def gold_state(benchmark: str) -> dict:
    if benchmark not in GOLD_STATE:
        raise KeyError(f"no gold state for {benchmark}")
    return GOLD_STATE[benchmark]


def empty_state() -> dict:
    return {
        "schema_version": "C-v0.1",
        "goals": [], "tasks": [], "decisions": [], "entities": [],
        "facts": [], "events": [], "failures": [], "dependencies": [],
        "current_state": {},
    }


def gold_to_c_fidelity(benchmark: str, serialized: str) -> dict:
    """Verify the gold state, once serialized, still carries every fact that is
    BINDING at S2. MUST be 1.0 (by construction); anything less is a C
    schema/serializer bug and Phase 2 must stop before running S2.

    Only exact_identifier / exact_value / structural are checked: negative
    ("don't implement now") and temporal_scope ("deferred to next session")
    are S1-temporal and MUST be absent from the S2 gold state.
    """
    binding = {"exact_identifier", "exact_value", "structural"}
    results = {}
    for f in metrics.GOLD[benchmark]["facts"]:
        if f["type"] in binding:
            results[f["id"]] = metrics.check_fact(f, serialized, serialized)
    return results