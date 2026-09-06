"""Stage 0.5 forensic sweep: for every run in the ledger, extract what S2
was told, what the eval showed, and whether the decision was present."""

import json
import re
from pathlib import Path

rows = []
for run in sorted(Path("results/stage0_4").glob("*-*")):
    if not (run / "session_2.json").exists():
        continue
    s2 = json.loads((run / "session_2.json").read_text())
    s1 = json.loads((run / "session_1.json").read_text())
    summary = json.loads((run / "summary.json").read_text())
    cond = summary["condition"]
    ctx = s2["context_artifact"]["text"]
    evaluation = s2["evaluation"]
    has_path = "/reports/summary" in ctx
    has_pagesize = bool(re.search(r"page_size['\"]?\s*[=: ]+\s*7", ctx)
                        or re.search(r"page\s*size[^.\n]{0,20}\b7\b", ctx, re.I))
    has_reports_key = bool(re.search(r"['\"]reports['\"]", ctx)) or ("'reports'" in ctx)
    fails = [ln for ln in (evaluation.get("tail") or "").splitlines()
             if "FAILED" in ln or "Error" in ln]
    rows.append({
        "run_id": summary["run_id"],
        "condition": cond,
        "seed": next((r for r in json.loads(
            Path("results/stage0_4/summary.json").read_text())
            ["runs"] if r["run_id"] == summary["run_id"]), {}).get("seed"),
        "success": summary.get("all_evaluations_passed", False)
                   and not any(r for r in [s2.get("agent_error")] if r),
        "s2_ctx_tokens": s2["context_artifact"]["token_count"],
        "s2_ctx_truncated": s2["context_artifact"]["truncated"],
        "ctx_has_path": has_path,
        "ctx_has_page_size": has_pagesize,
        "ctx_has_reports_key": has_reports_key,
        "s2_eval_passed": evaluation["passed"],
        "s2_eval_failures": fails[:4],
        "s2_agent_error": s2.get("agent_error"),
        "s1_eval_passed": s1["evaluation"]["passed"],
    })

for r in rows:
    print(f"{r['run_id']}  cond={r['condition']} seed={r['seed']} "
          f"success={r['success']} tok={r['s2_ctx_tokens']} "
          f"tr={'Y' if r['s2_ctx_truncated'] else '-'} "
          f"path={'Y' if r['ctx_has_path'] else 'N'} "
          f"ps7={'Y' if r['ctx_has_page_size'] else 'N'} "
          f"shape={'Y' if r['ctx_has_reports_key'] else 'N'}")
    for f in r["s2_eval_failures"]:
        print(f"    fail: {f}")
