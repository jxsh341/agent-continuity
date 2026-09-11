# Extraction Characterization (Phase 1)

Deterministic evaluation of the frozen extractor against gold standards derived
from the frozen benchmark CRITICAL_FACTS. No LLM judge. These scripts measure;
they do not modify C, B, benchmarks, models, or Stage 1A results.

## Layout

- `gold.py` — canonical facts per benchmark, typed by fidelity category
  (exact_identifier / exact_value / structural / negative_instruction /
  temporal_scope).
- `metrics.py` — pure deterministic matchers + per-extraction and aggregate
  recall scoring. Recall is reported **only over parse-successful extractions**;
  parse failure is captured separately as `parse_rate`.
- `evaluate.py` — replays the saved stratification outputs (`--replay`, default)
  or re-runs extraction (`--extract`), writes `results/extraction_eval/*.json`.

## Methodology notes

- Categories with zero gold facts are reported `None` ("n/a"), never 100%/0%.
- `structural` recall checks that all canonical component tokens are present in
  the serialized state.
- `negative_instruction` recall checks the design token is co-located with a
  negation in the raw output.
- `temporal_scope` recall checks a scope marker (next/future/later/implementation
  time) is present.

## Current result (Nemotron, frozen, n=129 transcripts)

| benchmark | parse | ident | value | structural | negative | scope | overall |
|---|---|---|---|---|---|---|---|
| fastapi | 76% | 97% | 90% | 68% | 97% | 100% | 91% |
| schema_migration | 87% | 78% | n/a | 13% | 44% | 33% | 49% |
| config_env | 93% | 80% | 50% | n/a | 45% | 92% | 70% |

Interpretive reading (held separate from the numbers):

- **fastapi** extracts near-perfectly when it parses; its residual weakness is
  JSON parse rate (76%).
- **schema_migration** parses well but loses **structural** fidelity (13%) — the
  column set (id/event/created_at) is rarely preserved intact.
- **config_env** parses best but drops the **exact value** (`42`, 50%) and shows a
  weak negative-instruction recall (45%) — the "payload inside a deferral" gap.