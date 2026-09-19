import json
import os
from pathlib import Path

ROOT = Path(".")
BENCHES = ["fastapi", "entity_relationship", "evolving_state"]


def classify_infra(err: str | None) -> str | None:
    if not err:
        return None
    s = str(err)
    if "404" in s:
        return "INFRA_404"
    if "timeout" in s.lower():
        return "INFRA_TIMEOUT"
    if "503" in s:
        return "INFRA_503"
    return "INFRA_OTHER"


def analyze_cell(run_dir: Path, bench: str) -> dict | None:
    # attempt expected files
    s1 = run_dir / "session_1.json"
    s2 = run_dir / "session_2.json"
    cfg = run_dir / "config.json"
    if not (s1.exists() and s2.exists() and cfg.exists()):
        return {
            "run_id": run_dir.name,
            "benchmark": bench,
            "condition": None,
            "budget": None,
            "seed": None,
            "endpoint_health": "MISSING_FILES",
            "execution_status": "incomplete",
            "scientific_outcome": None,
            "notes": "missing session_1/2/config.json"
        }

    cfgd = json.loads(cfg.read_text())
    s1d = json.loads(s1.read_text())
    s2d = json.loads(s2.read_text())

    s1_err = s1d.get("agent_error")
    s2_err = s2d.get("agent_error")

    # endpoint health: only if we actually launched S2 and it failed there; S1 error => infra during s1.
    infra = None
    if s1_err:
        infra = classify_infra(s1_err)
    elif s2_err:
        infra = classify_infra(s2_err)

    # evaluate S2 scientific outcome when infra OK and evaluation exists
    eval2 = s2d.get("evaluation") or {}
    s1_ok = (s1d.get("evaluation") or {}).get("passed") is True
    if infra:
        outcome = None
        status = "endpoint_failure"
    else:
        status = "completed"
        if s1_ok and eval2.get("passed") is True:
            outcome = "success"
        else:
            outcome = "failure"

    return {
        "run_id": run_dir.name,
        "benchmark": bench,
        "condition": cfgd["config"]["condition"],
            "budget": cfgd["config"]["context_budget"],
        "seed": cfgd["config"]["run_seed"],
        "endpoint_health": infra or "OK",
        "execution_status": status,
        "s1_tests_passed": s1_ok,
        "s2_context_tokens": (s2d.get("context_artifact") or {}).get("token_count"),
        "s2_context_truncated": (s2d.get("context_artifact") or {}).get("truncated"),
        "s2_error": s2_err,
        "scientific_outcome": outcome,
        "notes": None,
    }


def main():
    out_records = []
    for bench in BENCHES:
        p = Path(f"results/phase4_{bench}")
        if not p.exists():
            continue
        for run_dir in sorted(p.glob("*-*")):
            if run_dir.is_dir():
                cell = analyze_cell(run_dir, bench)
                if cell:
                    out_records.append(cell)

    out = Path("results/phase4_audit")
    out.mkdir(exist_ok=True)
    # jsonl for every cell
    with open(out / "ledger.jsonl", "w") as f:
        for r in out_records:
            f.write(json.dumps(r) + "\n")
    # summary table
    by_health = {}
    by_condition = {}
    for r in out_records:
        by_health.setdefault(r["endpoint_health"], 0)
        by_health[r["endpoint_health"]] += 1
        key = (r["benchmark"], r["condition"], r["budget"], r["seed"], r["endpoint_health"], r["execution_status"], r["scientific_outcome"])
        by_condition.setdefault(r["condition"], []).append(r)
    report = []
    report.append(f"TOTAl cells: {len(out_records)}")
    report.append("\nEndpoint health breakdown:")
    for k, v in by_health.items():
        report.append(f"  {k}: {v}")
    report.append("\nHealthy cells by condition/benchmark (only HEALTHY cells count toward sci outcome):")
    for cond in ["A", "B", "C", "D"]:
        cells = [r for r in out_records if r["condition"] == cond and r["endpoint_health"] == "OK" and r["execution_status"] == "completed"]
        succ = sum(1 for c in cells if c["scientific_outcome"] == "success")
        fail = sum(1 for c in cells if c["scientific_outcome"] == "failure")
        report.append(f"  {cond}: healthy={len(cells)} success={succ} failure={fail}")
    # Differences from summary.json
    summaries = {}
    for bench in BENCHES:
        sj = Path(f"results/phase4_{bench}/summary.json")
        if sj.exists():
            summaries[bench] = json.loads(sj.read_text())["runs"]
    mismatches = []
    for bench in BENCHES:
        if bench not in summaries:
            continue
        for r in out_records:
            if r["benchmark"] != bench:
                continue
            row = next((x for x in summaries[bench] if x.get("run_id") == r["run_id"]), None)
            if not row:
                mismatches.append((bench, r["run_id"], "not in summary.json"))
    report.append("\nsummary.json discrepancies (rows missing from summary):")
    report.extend([f"  {m}" for m in mismatches] or ["  none"])
    with open(out / "analysis.txt", "w") as f:
        f.write("\n".join(report))
    print("wrote", out / "ledger.jsonl", out / "analysis.txt")


if __name__ == "__main__":
    main()