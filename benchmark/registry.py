"""Benchmark registry (Stage 1.0 freeze). Adding a benchmark here is a
protocol event; modules are frozen independently of condition code."""

from __future__ import annotations

from benchmark import cache_policy_v1, config_env, entity_relationship_v1, evolving_state_v1, fastapi_repo, schema_migration

BENCHMARKS = {
    "fastapi": fastapi_repo,
    "schema_migration": schema_migration,
    "config_env": config_env,
    "cache_policy": cache_policy_v1,
    "entity_relationship": entity_relationship_v1,
    "evolving_state": evolving_state_v1,
}


def get(name: str):
    if name not in BENCHMARKS:
        raise KeyError(f"unknown benchmark: {name}")
    return BENCHMARKS[name]
