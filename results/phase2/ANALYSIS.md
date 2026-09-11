# Phase 2 Analysis — Reliable-Extraction (Gold) C Representation

Purpose: evaluate the frozen C-v0.1 structured representation + serializer with
the stochastic extraction layer removed (gold state derived from frozen
CRITICAL_FACTS), so the representation itself is the measured variable.

Instrument: gold state -> C-v0.1 normalization -> frozen serializer -> S2 agent
(muse-glimmer-30b, 80 iters) -> hidden tests. No LLM extraction, no new prompt.
S2-only (reference S1 applied deterministically). Fresh workspace + process.

Gold-to-C fidelity gate: verified 100% for all three benchmarks (only the
S2-binding fact types exact_identifier/exact_value/structural are checked;
negative_instruction and temporal_scope are S1-temporal and correctly absent).

## Result (18 cells)

| benchmark | 2048 | 8192 | total |
|---|---|---|---|
| fastapi | 3/3 | 3/3 | 6/6 |
| schema_migration | 3/3 | 3/3 | 6/6 |
| config_env | 1/3 | 2/3 | 3/6 |

## Findings

1. **Representation is validated.** With gold state, C completes the hidden task
   at 6/6 on fastapi and 6/6 on schema_migration — the two benchmarks where
   Stage 1A C failed purely because the extractor dropped/paraphrased facts. The
   frozen schema + serializer, when supplied correct state, drive the S2 agent to
   the correct implementation. No extraction, no retrieval, ~85-token context.

2. **config_env residual is agent-execution, not representation.** The 3 failing
   cells all show 100% gold-to-C fidelity (env var, key, and value 42 present in
   context), yet fail `test_default_absent_without_env`. The S2 agent recovered
   the primary fact (mapping) but added the config key unconditionally instead of
   gating on env presence — a code-correctness subtlety, isolated from both
   extraction and the structured-state representation. This matches the oracle
   result exactly.

3. **Context-budget insensitivity (expected).** The serialized gold state is ~85
   tokens, so 2048 vs 8192 makes no difference — correct, since C's representation
   is intrinsically compact. This is the flip side of D's budget-dependence.

## Causal-chain decomposition (three named layers)

- extraction (parse + semantic omission) — the Stage 1A confound, now removed.
- representation/serializer — validated sound (gold-to-C fidelity 100%, and S2
  uses the state when given).
- agent execution — a small, task-specific residual (config_env default-gating).

## Conclusion (for the record, not a protocol change)

The structured-state representation is NOT the bottleneck. Its Stage 1A
underperformance was upstream extraction. This supports naming the research object
"structured state + reliable extraction layer" and proceeding to a fair
cross-condition comparison where the representation is compared at equal
information fidelity.

Artifacts: results/phase2/<benchmark>/cell_<seed>_<budget>.json