"""Stage 3 forensic rebuild + audit: ground truth from run dirs.

Reconstructs the ledger from results/stage3_<bench>/*/run directories
(the on-disk evidence), not from the summary.json files. This is the
canonical source for analysis.
"""
import json, glob, os, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from benchmark.registry import BENCHMARKS

BENCHES = ["fastapi", "schema_migration", "config_env"]

def rebuild():
    out = {}
    for bench in BENCHES:
        rows = []
        for run_dir in sorted(glob.glob(f"results/stage3_{bench}/*-*")):
            s1 = os.path.join(run_dir, "session_1.json")
            s2 = os.path.join(run_dir, "session_2.json")
            cfg = os.path.join(run_dir, "config.json")
            if not (os.path.exists(s1) and os.path.exists(s2)):
                rows.append({
                    "run_id": os.path.basename(run_dir),
                    "s1_exists": os.path.exists(s1),
                    "s2_exists": os.path.exists(s2),
                    "incomplete": True,
                })
                continue
            c = json.load(open(cfg))
            s1d = json.load(open(s1))
            s2d = json.load(open(s2))
            sm = os.path.join(run_dir, "summary.json")
            smd = json.load(open(sm)) if os.path.exists(sm) else {}
            taskfile = os.path.join(run_dir, "session_2.json")
            cond = c["config"]["condition"]
            budget = c["config"]["context_budget"]
            seed = c["config"]["run_seed"]
            ctx = s2d.get("context_artifact", {}) or {}
            eval2 = s2d.get("evaluation", {}) or {}
            entry = {
                "benchmark": bench,
                "run_id": os.path.basename(run_dir),
                "condition": cond,
                "budget": budget,
                "seed": seed,
                "s1_visible_tests_passed": s1d.get("evaluation", {}).get("passed"),
                "s2_agent_error": s2d.get("agent_error"),
                "s2_ctx_tokens": ctx.get("token_count"),
                "s2_ctx_truncated": ctx.get("truncated"),
                "s2_provenance": ctx.get("provenance"),
                "s2_all_tests_passed": eval2.get("passed"),
                "eval_tail": eval2.get("tail", "")[:0],  # recorded in s2 full
                "success": bool(
                    s1d.get("evaluation", {}).get("passed")
                    and eval2.get("passed")
                    and not s2d.get("agent_error")
                ),
            }
            rows.append(entry)
        out[bench] = rows
    return out

def main():
    out = rebuild()
    Path("results/stage3").mkdir(parents=True, exist_ok=True)
    outdir = Path("results/stage3/ledgers")
    outdir.mkdir(exist_ok=True)
    for bench, rows in out.items():
        p = outdir / f"{bench}.json"
        p.write_text(json.dumps(rows, indent=2))
        complete = [r for r in rows if not r.get("incomplete")]
        n_by = {}
        for r in complete:
            key = (r["condition"], r["budget"])
            n_by.setdefault(key, []).append(r["success"])
        print(f"== {bench}")
        for cond in "ABCD":
            for budget in [1024, 2048, 4096, 8192]:
                k = (cond, budget)
                if k in n_by:
                    vals = n_by[k]
                    print(f"  {cond}@{budget}: {sum(vals)}/{len(vals)}")

if __name__ == "__main__":
    main()