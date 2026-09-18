# Phase 4 — Controlled-Extraction Causal Test (Pre-Registration)

Status: **FROZEN DESIGN. Not executed.** This document defines the experiment
BEFORE any Phase 4 run. Any change after execution requires a protocol
amendment (AMD-003+) and cannot retroactively relabel Phase 4 results.

## Baseline (frozen in Stage 3, never changed retroactively)

240 cells @ commit b7f6801:

| Condition | Success |
|---|---|
| A (no memory) | 7/60 |
| B (Mem0 retrieval) | 6/60 |
| C (structured state + real extractor) | 15/60 |
| D (raw history) | 6/60 |

This baseline is the reference for the causal driver tests below.

## Research question

"If extraction reliability is controlled, does structured continuity produce a
statistically robust advantage over conventional memory (B) and raw-history (D)
baselines across independent tasks and context budgets?"

## Hypotheses

H1 (primary): Oracle-C > B at matched context budgets, across benchmarks.
  Null: no significant difference.
H2: The gap (C-real vs Oracle-C) is predicted by extraction fidelity
  (measurable from `recovery_telemetry` + `fact_fidelity`).
H3 (efficiency): Oracle-C succeeds at lower context tokens than D/B at matched
  pass rate (success-of-token slope).

## Conditions (mutually exclusive; identical agent + environment)

- **A**: no cross-session context (negative control)
- **B**: Mem0 retrieval (unchanged; same nemotron extractor + mem0 action)
- **C-real**: structured state via frozen Nemotron; AMD-002 recoverie allowed
- **C-reliable**: verified canonical truth state (from benchmark
  CRITICAL_FACTS) serialized through the frozen C serializer — same schema +
  serializer as C-real. Previously "gold-C", renamed Oracle-C.
- **D**: raw truncated transcript

Naming rule: "oracle" is the causal upper bound. Only C-real is the deployable system.

## Task suite (Phase 4A)

Add 8–12 independent memory-critical engineering tasks, distributed across:
exact identifiers, exact values, config relationships, architectural decisions,
negative instructions, temporal constraints, multi-step dependencies, prior
failures, entity relationships, evolving state. The goal: make it hard to argue
results come from quirks of the three Stage-1 benchmarks.

All new tasks share the Stage-1 format:
fresh workspace; conversation-limited via clear benchmark design; hidden tests;
SCRUBBED memory-surface AGENTS.md. Each task carries CRITICAL_FACTS annotations.

## Endpoints (pre-registered, ordered)

Primary: **S2 hidden-test success.** (binary, deterministic)

Secondary:
- critical-fact recall (per-fact category: identifier, value, structural,
  negative, temporal)
- extraction parse rate (C-real only; from recovery telemetry)
- context token count (required vs truncated)
- truncated rate
- conditional success (× critical-fact present)
- per-budget success curve

## Sample size and statistics

- Per-benchmark, per-condition, per-budget: 5–10 seeds.
- Primary test (Oracle-C vs B at each budget): two-proportion z-test or
  Fisher exact; report e_s (small/medium/large) as predefined thresholds
  (0.2/0.5/0.8 absolute-use criterion for ≤5 seeds).
- Multiplicity: Benjamini-Hochberg across benchmarks (per-budget cluster),
  controlled at q=0.05.

## Exclusion rules (pre-registered)

- `infrastructure_failure` cells (runner/endpoint crash): re-run, not counted.
- `agent_error` cells: counted as failures for that cell.
- dirty-tree or non-frozen-code outputs: rejected (must be at the pinned
  commit of the launch).
- No mid-mission "optimization" of extraction, schema, task, or evaluator.

## Efficiency analysis (Phase 4D)

task-success, tokens, tokens-per-success, fidelity-vs-budget tails.
Task 4D is where the "structured state is cheaper" product thesis lives.

## What is explicitly NOT in Phase 4

- No extractor improvement; Nemotron is unchanged (its cost is quantified,
  not hidden).
- No new C schema (C-v0.1 frozen) or serializer change.
- No B rewrite; B remains Mem0 as deployed.
- No changes to Stage 3, its data, or its interpretation.
"B" and "D" should be expected to score poorly on some tasks: we're testing
representational continuity, shortcut-friendly tasks are noise floor.

## Phase 4B pilot (smoke)

3 benchmarks × {A,B,C-real,C-Oracle,D} × {2048,8192} × 3 seeds ≈ 90 cells,
built only to validate the machinery (task dispatch, budget apply, ledgers,
statistics inputs).

## Language in later docs

- "Oracle-C" = verified canonical state, causal upper bound, not a deployable.
- "C-real" = deployable + Nemotron. Benchmark noshorts mixing name changes.
