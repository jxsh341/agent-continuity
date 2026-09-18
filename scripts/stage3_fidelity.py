"""Stage 3 fidelity analysis: for each run dir, evaluate the S2 context
artifact against the benchmark's critical facts and fold in success."""
import json, glob, os, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from benchmark.registry import BENCHMARKS
from extraction.gold import GOLD

BENCH_LIST = ["fastapi", "schema_migration", "config_env"]


def load_runs():
    rows = []
    for bench in BENCH_LIST:
        mod = BENCHMARKS[bench]
        for run_dir in sorted(glob.glob(f"results/stage3_{bench}/*-*")):
            s2 = os.path.join(run_dir, "session_2.json")
            cfg = os.path.join(run_dir, "config.json")
            if not os.path.exists(s2):
                continue
            s2d = json.load(open(s2))
            c = json.load(open(cfg))
            s1d = json.load(open(os.path.join(run_dir, "session_1.json")))
            text = (s2d.get("context_artifact") or {}).get("text", "")
            # evaluate fidelity using the benchmark's CRITICAL_FACTS checks
            ff = {}
            for f in mod.CRITICAL_FACTS:
                try:
                    ff[f["id"]] = bool(f["check"](text))
                except Exception:
                    ff[f["id"]] = None
            entry = {
                "benchmark": bench,
                "condition": c["config"]["condition"],
                "budget": c["config"]["context_budget"],
                "seed": c["config"]["run_seed"],
                "run_id": os.path.basename(run_dir),
                "success": bool(
                    s1d.get("evaluation", {}).get("passed")
                    and (s2d.get("evaluation") or {}).get("passed")
                    and not s2d.get("agent_error")
                ),
                "ctx_tokens": (s2d.get("context_artifact") or {}).get("token_count"),
                "truncated": (s2d.get("context_artifact") or {}).get("truncated"),
                "fact_fidelity": ff,
            }
            rows.append(entry)
    return rows

def bench_means(rows, bench, cond, budget):
    sub = [r for r in rows if r["benchmark"] == bench and r["condition"] == cond and r["budget"] == budget]
    if not sub: return None
    pass_rate = sum(1 for r in sub if r["success"]) / len(sub)
    mean_ctx = sum((r["ctx_tokens"] or 0) for r in sub) / max(1, (len(sub)))
    # aggregate per benchmark: which CF ids exist? benchmark has its own ids only
    b = BENCHMARKS[bench]
    cf_ids = [f["id"] for f in b.CRITICAL_FACTS]
    cf = {}
    for cid in cf_ids:
        vals = [r["fact_fidelity"].get(cid) for r in sub if r["fact_fidelity"].get(cid) is not None]
        cf[cid] = (sum(vals)/len(vals)) if vals else None
    trunc = sum(1 for r in sub if r.get("truncated")) / len(sub)
    return {"n": len(sub), "pass_n": sum(1 for r in sub if r["success"]), "pass_rate": pass_rate, "ctx": mean_ctx, "trunc": trunc, "cf": cf}

def main():
    rows = load_runs()
    BENCHES = ["fastapi", "schema_migration", "config_env"]
    BUDGETS = [1024, 2048, 4096, 8192]
    Path("results/stage3").mkdir(exist_ok=True)
    out_j = Path("results/stage3/fidelity_analysis.json")
    out_j.write_text(json.dumps(rows, indent=2))
    # build markdown
    lines = ["# Stage 3 Fidelity Analysis", ""]
    for bench in BENCHES:
        lines.append(f"## {bench}")
        lines.append("")
        lines.append("| cond | budget | cells | success | ctx_tokens | trunc% | fact-fidelity |")
        lines.append("|---|---|---|---|---|---|---|")
        for cond in ["A","B","C","D"]:
            for budget in BUDGETS:
                m = bench_means(rows, bench, cond, budget)
                if m is None:
                    continue
                cf_s = ", ".join(
                    f"{k}={v:.0%}" if v is not None else f"{k}=n/a"
                    for k, v in m["cf"].items()
                )
                lines.append(f"| {cond} | {budget} | {m['n']} | {m['pass_n']}/{m['n']} ({m['pass_rate']:.0%}) | {m['ctx']:.0f} | {m['trunc']:.0%} | {cf_s} |")
        lines.append("")
    lines.append("## Totals")
    cond_order = ["A","B","C","D"]
    for cond in cond_order:
        allc = [r for r in rows if r.get("condition") == cond]
        p = sum(1 for r in allc if r["success"])
        lines.append(f"- {cond}: {p}/{len(allc)}  ({p/len(allc):.1%})")
    Path("results/stage3/fidelity_analysis.md").write_text("\n".join(lines))
    print("\n".join(lines))

if __name__ == "__main__":
    main()