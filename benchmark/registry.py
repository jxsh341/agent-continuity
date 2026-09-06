"""Benchmark registry (Stage 1.0 freeze). Adding a benchmark here is a
protocol event; modules are frozen independently of condition code."""

from __future__ import annotations

from benchmark import config_env, fastapi_repo, schema_migration

BENCHMARKS = {
    "fastapi": fastapi_repo,
    "schema_migration": schema_migration,
    "config_env": config_env,
}


def get(name: str):
    if name not in BENCHMARKS:
        raise KeyError(f"unknown benchmark: {name}")
    return BENCHMARKS[name]
