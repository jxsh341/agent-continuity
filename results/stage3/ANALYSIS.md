# Stage 3 Analysis — Main A/B/C/D Cross-Condition Comparison

**Data source:** rebuilt from `results/stage3_<bench>/<run>/` directories
(session_1.json, session_2.json, config.json) — **run dirs**, not the
summary.json ledgers (one of which was damaged and repaired).

**Matrix:** 3 benchmarks × 4 conditions × 4 budgets × 5 seeds = 240 cells,
**all present and complete**, 0 infra-failure cells.

Frozen pins: OpenHands SDK @ cca903c8, agent = `meta/muse-glimmer-30b`,
extractor = `nvidia/nemotron-3-ultra-550b-a55b` (T=0, top_p=1),
iteration cap 80/session,  cl100k_base tokens, AMD-002 active
(bounded parse/schema recovery, ≤3 attempts).

## Outcome Grid

| benchmark | budget | A | B | C | D |
|---|---|---|---|---|---|
| fastapi | 1024 | 0/5 | 2/5 | 2/5 | 0/5 |
| fastapi | 2048 | 3/5 | 1/5 | 1/5 | 0/5 |
| fastapi | 4096 | 3/5 | 2/5 | 2/5 | 0/5 |
| fastapi | 8192 | 1/5 | 1/5 | 1/5 | 0/5 |
| schema_migration | 1024 | 0/5 | 0/5 | 0/5 | 0/5 |
| schema_migration | 2048 | 0/5 | 0/5 | 2/5 | 0/5 |
| schema_migration | 4096 | 0/5 | 0/5 | 0/5 | 0/5 |
| schema_migration | 8192 | 0/5 | 0/5 | 0/5 | 1/5 |
| config_env | 1024 | 0/5 | 0/5 | 2/5 | 0/5 |
| config_env | 2048 | 0/5 | 0/5 | 1/5 | 2/5 |
| config_env | 4096 | 0/5 | 0/5 | 1/5 | 2/5 |
| config_env | 8192 | 0/5 | 0/5 | 3/5 | 2/5 |

**Per-benchmark totals (out of 20 each for A..D):**

| cond | fastapi | schema_migration | config_env |
|---|---|---|---|
| A | 7/20 | 0/20 | 0/20 |
| B | 6/20 | 0/20 | 0/20 |
| C | 6/20 | 2/20 | 7/20 |
| D | 0/20 | 1/20 | 5/20 |

## Findings (strictly from the ledger)

1. **A is not a pure floor on fastapi.** A passed 7/20 (all under the
   fastapi benchmark, 2048 and 4096 budgets). That is consistent with the
   known Stage 1.5 caveat (fastapi is easily recoverable from in-repo
   signals) — **not** evidence that A is memory-free. On the other two
   benchmarks A is 0/20, as designed.

2. **B never wins on the newer two benchmarks.** B = 0/20 on
   schema_migration and config_env. Of the six B wins, all are on fastapi.

3. **C does not uniformly beat baselines.** Findings per benchmark:
   - fastapi: C = 6/20. A dominates (7/20). With A doable, fastapi has a
     large discoverability signal.
   - schema_migration: C = 2/20. D = 1/20. Neither beats the other
     meaningfully; both are low.
   - config_env: C = 7/20 ties/bests D = 5/20 (and A/B each 0/20).
     B remains not the winner of these two.

4. **The extractor-layer analysis already proved the failure mechanism
   for C.** Strip out that confound (Phase 2 gold-C oracle) and *the same
   structured representation succeeds* on the same benchmarks. That is not
   shown in this grid (Phase 3a runs the *native* pipeline). If we trust
   Stage 0.x diagnostic, this grid's C mix of failures is mostly
   extraction-driven, not representation-driven.

## Integrity notes (critical)

- The Stage 3 run's per-benchmark summary.json for fastapi had an append
  bug in the matrix runner: entries were written twice for the same
  (condition,budget,seed). I rebuilt `results/stage3/*/ledgers/*.json`
  from the per-run directories into `results/stage3/ledgers/`.
- I previously mis-recorded a wrong table (assumed more C wins on
  schema_migration) — corrected above now that the forensic rebuild is
  the source of truth.

## What the data actually supports

These three benchmarks at four budgets do **not** give uniform evidence
for "structured state (C) crushes D (raw history) or B (semantic
retrieval)". What emerges:

1. **On a genuinely memory-critical task** where the relevant design fact
   crosses the boundary only via text, **C ≥ D** (config_env, be
   consistent: C = 7/20, D = 5/20).
2. **On a structurally brittle task** with a small implementation
   surface and strict verifier (schema_migration), everyone is poor;
   that's a task difficulty effect more than a kit effect.
3. **On a discoverable task** (fastapi), A is surprisingly strong —
   because the answer is sometimes guessable from repo context. That is a
   near-experimental-design issue, not a C problem.

So C's advantage appears **task-dependent**, and extractor fidelity
remains a key confound in C real numbers. More experiments are needed to
decommon this confound for replicable conclusions.

## Frozen elements (unchanged by Stage 3)

- No change to `benchmark/*`, `conditions/*`, `extractors/*`,
  `serialization/*`, prompts, models, budgets, evaluation. AMD-002 only
  affects how the extractor survives transient infrastructure failures.

## Next step

The Stage 3 grid is a diagnostic checkpoint, not a final verdict. The
correct follow-up is to let the experiment *tell us* what happened by
aggregating across all 240 cells with error bars, then we evaluate
whether the results justify Stage 4 / Stage-4B.
