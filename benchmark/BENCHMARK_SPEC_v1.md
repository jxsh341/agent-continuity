# Benchmark Specification v1.0 (FROZEN for Stage 1)

All benchmarks share one shape: two-session engineering tasks over a small
real repository; a conversation-only design decision delivered in session 1
that is required by hidden tests injected after session 2.

## Fact-type taxonomy

| type | meaning | required fidelity |
|---|---|---|
| exact_identifier | path/name/key string | byte-exact |
| exact_value | numeric/string value | byte-exact |
| structural | required composite shape | all components present |
| conceptual | behavior/strategy | semantic |
| negative_instruction | "do not do X now" | scope-authenticated |
| temporal_scope | when a decision takes effect | semantic + scope |

## Benchmarks

### 1. fastapi (existing, id: fastapi_shopapi_v1)
S1: implement DELETE /items/{id}; S2: implement /reports/summary.
Critical facts: path (exact_identifier), page_size=7 (exact_value),
'reports' response key (structural), defer-now (negative_instruction).

### 2. schema_migration (v1)
Repo: toy sqlite migration runner.
S1: implement apply_pending(); S2: create the decided migration.
Critical facts:
- `003_add_audit_log.sql` filename (exact_identifier)
- table `audit_log` (exact_identifier)
- columns id,event,created_at (structural)
- defer-now (negative_instruction)

### 3. config_env (v1)
Repo: layered config loader.
S1: implement env override layer; S2: wire the decided env var mapping.
Critical facts:
- env var `SHOPAPI_RATE_LIMIT_RPS` (exact_identifier)
- config key `rate_limit_rps` (exact_identifier)
- value `42` (exact_value)
- defer-now (negative_instruction)

## Evaluation

Deterministic only: per-session pytest; session 2 adds injected hidden tests
asserting the exact facts above. No LLM judges. Contamination scan after S1
(forbidden strings must not appear in repo).

## Freeze

Changes to benchmarks listed here require a protocol amendment and a new spec
version. A/B/C/D conditions, agent model, and prompts are pinned separately in
configs/framework_pin.json and the experiment Git history.
