"""Gold-state extraction standards (Phase 1: extraction characterization).

Each benchmark's gold facts are DERIVED from the frozen benchmark CRITICAL_FACTS,
not invented. Each fact carries a `type` (one of the fidelity categories) and the
canonical value that a CORRECT extraction must preserve. Comparison is
deterministic (no LLM judge) — see metrics.py.

Freeze: these gold standards are pinned to the frozen benchmarks. Changing a
benchmark's critical facts (a protocol event) changes the gold standard too.
"""

from __future__ import annotations

# Canonical facts per benchmark. `match` names the deterministic matcher
# (see metrics.py), `value` is the canonical expected value.
GOLD: dict[str, dict] = {
    "fastapi": {
        "facts": [
            {"id": "E-fp-1", "type": "exact_identifier",
             "value": "/reports/summary", "match": "exact"},
            {"id": "E-fp-2", "type": "exact_identifier",
             "value": "page_size", "match": "exact"},
            {"id": "S-fp-1", "type": "structural",
             "value": ["reports", "category", "count"], "match": "structural"},
            {"id": "V-fp-1", "type": "exact_value",
             "value": "7", "match": "word"},
            {"id": "N-fp-1", "type": "negative_instruction",
             "value": "reports", "match": "negative"},
            {"id": "T-fp-1", "type": "temporal_scope",
             "value": "next", "match": "temporal"},
        ],
    },
    "schema_migration": {
        "facts": [
            {"id": "E-sm-1", "type": "exact_identifier",
             "value": "003_add_audit_log.sql", "match": "exact"},
            {"id": "E-sm-2", "type": "exact_identifier",
             "value": "audit_log", "match": "exact"},
            {"id": "S-sm-1", "type": "structural",
             "value": ["id", "event", "created_at"], "match": "structural"},
            {"id": "N-sm-1", "type": "negative_instruction",
             "value": "audit_log", "match": "negative"},
            {"id": "T-sm-1", "type": "temporal_scope",
             "value": "next", "match": "temporal"},
        ],
    },
    "config_env": {
        "facts": [
            {"id": "E-ce-1", "type": "exact_identifier",
             "value": "SHOPAPI_RATE_LIMIT_RPS", "match": "exact"},
            {"id": "E-ce-2", "type": "exact_identifier",
             "value": "rate_limit_rps", "match": "exact"},
            {"id": "V-ce-1", "type": "exact_value",
             "value": "42", "match": "word"},
            {"id": "N-ce-1", "type": "negative_instruction",
             "value": "rate_limit", "match": "negative"},
            {"id": "T-ce-1", "type": "temporal_scope",
             "value": "next", "match": "temporal"},
        ],
    },
}

# Ordered category list used for reporting (stable ordering).
CATEGORIES = [
    "exact_identifier",
    "exact_value",
    "structural",
    "negative_instruction",
    "temporal_scope",
]