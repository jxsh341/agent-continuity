# agent-continuity-research

Stage-0 implementation scaffold for the frozen v0.1 agent-continuity experiment.

The first objective is mechanical: prove that A/B/C/D can run through the same
session runner with fresh processes, persistent condition-specific state, and
machine-checkable evaluation.

## Quick start

```bash
python -m venv .venv
# activate the environment
pip install -e .
pytest -q
```

The default test suite exercises the runner, state isolation, structured
continuity, token budgeting, and deterministic evaluation without requiring an
LLM API.

## Agent substrate

The coding agent is NOT implemented here. We use the external
**OpenHands Software Agent SDK** as a pinned, editable dependency
(cloned at `C:/Users/user/software-agent-sdk`, commit pinned in
`configs/framework_pin.json`). The SDK clone must stay clean; all
experiment logic lives in this repo.

```powershell
uv venv --python 3.13 .venv
uv pip install --python .venv/Scripts/python.exe `
  -e C:/Users/user/software-agent-sdk/openhands-sdk `
  -e C:/Users/user/software-agent-sdk/openhands-tools `
  -e C:/Users/user/software-agent-sdk/openhands-workspace
```

Boundary: OpenHands owns reasoning/tools/conversation; this repo owns
what context a fresh session starts with (conditions A/B/C/D) and token
accounting. No memory logic is added to the agent or its system prompt;
continuity enters only via the first user message (`agent/prompts.py`).

## Layout

- `agent/` — thin OpenHands adapter, model config, frozen session message
- `continuity/` — provider-neutral runner and memory interfaces
- `conditions/` — A/B/C/D implementations
- `evaluation/` — deterministic checks and metrics
- `benchmark/` — benchmark/task definitions
- `configs/` — immutable run configuration files (incl. SDK pin)
- `results/` — runtime artifacts (ignored by git except `.gitkeep`)
- `scripts/` — Stage-0 commands (`run_openhands_smoke.py` = Milestone 0.1)

## Next implementation step

Wire `LLMClient` to the chosen shared extractor/agent model and implement the
FastAPI task sequence after the harness passes its local tests.
