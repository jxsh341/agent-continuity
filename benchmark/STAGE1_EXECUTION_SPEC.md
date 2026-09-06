# Stage 1 Execution Specification (FROZEN)

Status: fixed before execution. Changes require a protocol amendment recorded in
`configs/amendments.json` and a new spec version.

## Hypothesis

Does structured cross-session state (C) improve task continuity relative to no
context (A), raw history (D), and semantic memory retrieval (B), across
memory-critical engineering tasks and context budgets?

## Stage 1A matrix (this execution)

| Axis | Values |
|---|---|
| Benchmarks | fastapi, schema_migration, config_env |
| Conditions | A, B, C, D |
| Budgets | 2048, 8192 |
| Seeds | 1–5 |
| Cells | 3 × 4 × 2 × 5 = 120 |

Rationale: 2048 is directly comparable with Stage 0.5; 8192 tests whether D's
failure is purely budget-driven and whether C's advantage persists when raw
history largely fits.

Stage 1B (budget curve: 1024, 4096) is considered only after 1A analysis.
Seed expansion to 10 is considered only where variance warrants.

## Frozen at execution time

- OpenHands SDK @ cca903c808f7d954f1749a1a91890476d2f0a107 (editable)
- Mem0 2.0.19 @ 19cb89aff472325c707f64b2f34ae6afdbf7faf7 (self-hosted)
- Agent model: openai/meta/muse-glimmer-30b
- Extractor model (B mem0 + C): nvidia/nemotron-3-ultra-550b-a55b,
  temperature 0.0, top_p 1.0, max_tokens 2048
- C schema: schemas/c_v0_1.json; extractor prompt: c-extraction-v1
- B: mem0 chunked add (8 msgs/chunk, ≤3 chunk attempts), native search
- D: raw history, oldest-first truncation
- A: empty context
- Session mechanics: fresh process per cell, fresh workspace per cell,
  session boundary = full process restart inside one cell
- Workspace-hygiene: memory-note files (AGENTS.md) scrubbed at every
  session boundary; contamination scan after S1
- Evaluation: deterministic pytest (visible S1; visible + injected hidden S2)
- Token accounting: cl100k_base via continuity.tokens
- Iteration cap: 80 per session
- LLM transport retries on transient failures: ≤3 attempts
- Experiment clean-tree guard: runs refuse to start with dirty tracked tree

## Cell outcome labels

- success: S1 visible tests pass AND S2 visible+hidden tests pass AND no
  agent error
- failure (condition outcome): S2 tests fail / agent error, with clean
  infrastructure
- infrastructure_failure: crash/timeout in conditions/runner/transport —
  recorded as such, repaired under AMD rules, cell rerun fresh
- Each cell also records fact_fidelity (per benchmark CRITICAL_FACTS against
  the S2 context artifact), context tokens, truncation, leak flags, both
  LLM metric blobs, wall time.

## Execution rules

- Resumable: a cell is complete only when its entry exists in the
  per-benchmark summary ledger; partial dirs are evidence only.
- No parameter, prompt, model, benchmark, or condition changes mid-Stage 1A.
- No interpretation or optimizations between cells.

## Analysis output (Stage 1.5, after matrix completes)

Per condition/benchmark/budget: pass rate, context-token distribution,
truncation rates, fact-fidelity breakdown, failure-mode classification
(extraction vs retrieval vs truncation vs agent), variance across seeds.
