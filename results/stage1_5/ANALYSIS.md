# Stage 1.5 Analysis — Results Artifact

Status: analysis of the completed 120-cell Stage 1A matrix. Observation only; not
accepted as evidence for/against the protocol hypotheses. No condition, benchmark,
prompt, model, budget, or evaluator was changed to reach these results.

## Integrity gate

- 120/120 cells present across three per-benchmark ledgers (fastapi 40, schema_migration 40, config_env 40).
- 0 cells marked `infrastructure_failure` in ledger rows.
- Extraction-level transport failures (HTTP 5xx in the nemotron extractor) were
  handled under AMD-001 (retry) for C and chunk-level retry for B; they are visible
  as *request-level* noise, recorded, not silently repaired.
- Experiment commit frozen across all cells; no leakage of design into workspace
  detected per contamination scan.

## Outcome grid (pass rate per condition@budget, 5 seeds each)

| benchmark | A@2048 | A@8192 | B@2048 | B@8192 | C@2048 | C@8192 | D@2048 | D@8192 |
|---|---|---|---|---|---|---|---|---|
| fastapi | 1 | 3 | 2 | 0 | 3 | 4 | 1 | 2 |
| schema_migration | 0 | 1 | 0 | 1 | 0 | 0 | 0 | 1 |
| config_env | 0 | 0 | 0 | 0 | 2 | 1 | 2 | 1 |

## Headline observations (mechanistic, not inferential)

### 1. A is not a clean floor everywhere
A (no memory) passed on fastapi@8192 (3/5) and occasionally elsewhere. This means
the fastapi implementation detail (`page_size=7`, path, shape) is, in some seeds,
recoverable by the S2 agent from the repository state or by inference — the
negative-control task is not uniformly memory-binding. This is a benchmark
sensitivity finding, not an A-behavior finding.

### 2. The binding constraint is now the extractor, not the representation
- On schema_migration, both C and B empty out at the extraction stage:
  - C/8192, C/2048: multiple seeds have `extraction_error = "extractor output is not parseable JSON"` (the nemotron extractor fails on the long 82-message transcripts), producing 0-token S2 context.
  - B/2048: multiple seeds stored **0 memories** across all chunks despite 3 add-attempts each.
- On config_env, B@2048 returned 0 context tokens in 3 of 5 seeds for the same reason.
- On fastapi, the same extractor worked, giving B and C real traction.

So the earlier Stage-0.5 signal ("C's weakness is extraction fidelity") has
generalized: for the two *new* benchmarks, extraction fidelity — not the choice
between structured/semantic/raw representation — is the dominant failure mode.

### 3. D remains truncation-limited, and the effect scales with budget
D's S2 context is bounded by the transcript size; at 2048 it truncates 7-8 of 10
cells per benchmark, at 8192 it mostly fits within budget (fastapi D@8192 hit 6059/6400/6829 tokens). D does not reliably carry the design under 2048.

## Fact-fidelity (C only, where extraction succeeded)

Per-cell `fact_fidelity` reports which critical facts were present in the C S2
context artifact:

- fastapi C: successes correlated with all facts present (`CF-page-size`,
  `CF-reports-shape` present). Failures correlated with `CF-reports-shape` or
  `CF-page-size` missing — extraction paraphrase, echoing C2/C3 in Stage 0.5.
- schema_migration C: `CF-columns`/`CF-migration-filename`/`CF-table-name` missing
  in most cells, matching the JSON-parse failures above.
- config_env C: `CF-config-key`/`CF-rate-value` missing in several cells.

## Causal-channel map

Wherever C succeeded (fastapi 3-4/5, config_env 2/5 at 2048), the sequence held:
S1 transcript -> extractor -> structured state (fact present) -> serializer ->
S2 context -> agent acted on the fact -> hidden tests pass. Where it failed, the
chain broke upstream at extraction, not at serialization or agent action.

## Failure-mode classification (dominant per condition)

- A: absence of context (benchmark-dependent leak on fastapi).
- B: extraction returns zero memories on transcripts where the design is embedded
  in long dialogue (schema_migration, config_env); otherwise retrieval-based
  variance (fastapi).
- C: extraction JSON non-parseability on long transcripts; otherwise faithful,
  with exact-identifier paraphrase as a secondary failure.
- D: budget/truncation.

## Separate from the above (not conclusions)

- Whether these differences constitute evidence for/against H1..H5 is deferred to
  a protocol-governed decision, not this artifact.

## Instrumentation caveat (recorded for integrity)

`CF-columns` uses substring checks (e.g. "id" is a substring of many words) and may
over-report presence in some cells. It is descriptive, not a graded metric; a
string-normalization fix (if any) must be a protocol amendment before reuse.

## Frozen items (unchanged)

OpenHands SDK cca903c8; Mem0 2.0.19 @ 19cb89a; agent model muse-glimmer-30b;
extractor nemotron-3-ultra-550b-a55b (T=0); C schema C-v0.1; c-extraction-v1;
budgets via cl100k_base; iteration cap 80; deterministic pytest evaluation.