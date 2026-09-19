"""Rebuild results/phase4_<benchmark>/summary.json from run dirs.

Each run dir has:
  config.json (contains task config incl. condition/budget/run_seed)
  session_1.json, session_2.json (with evaluation and context_artifact)
"""
import json, glob, os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

for BENCH in ("fastapi", "entity_relationship", "evolving_state"):
    out = []
    seen = {}
    for run_dir in sorted(glob.glob(f"results/phase4_{BENCH}/*-*")):
        s1 = os.path.join(run_dir, "session_1.json")
        s2 = os.path.join(run_dir, "session_2.json")
        cfg = os.path.join(run_dir, "config.json")
        if not (os.path.exists(s1) and os.path.exists(s2)):
            continue
        c = json.load(open(cfg))["config"]
        s1d = json.load(open(s1))
        s2d = json.load(open(s2))
        key = (c["condition"], c["context_budget"], c["run_seed"])
        cond = c["condition"]
        entry = {
            "run_id": os.path.basename(run_dir),
            "benchmark": BENCH,
            "condition": cond,
            "budget": c["context_budget"],
            "seed": c["run_seed"],
            "experiment_commit": c.get("experiment_commit"),
            "s1_visible_tests_passed": s1d.get("evaluation", {}).get("passed"),
            "s2_all_tests_passed": s2d.get("evaluation", {}).get("passed"),
            "decision_leaked_to_repo": c.get("decision_leaked_to_repo", False),
            "fact_fidelity": (s2d.get("context_artifact") or {}).get("provenance", {}).get("fact_fidelity", {}),
            "s2_context_tokens": (s2d.get("context_artifact") or {}).get("token_count"),
            "s2_context_truncated": (s2d.get("context_artifact") or {}).get("truncated"),
            "s2_agent_error": s2d.get("agent_error"),
            "success": bool(s1d.get("evaluation", {}).get("passed") and (s2d.get("evaluation") or {}).get("passed") and (not s2d.get("agent_error"))),
        }
        seen[key] = entry
    out = list(seen.values())
    target = Path(f"results/phase4_{BENCH}/summary.json")
    target.write_text(json.dumps({"runs": out}, indent=2))
    print(BENCH, len(out), "entries")
