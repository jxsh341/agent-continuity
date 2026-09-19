import json
from pathlib import Path

for bench in ["fastapi", "entity_relationship", "evolving_state"]:
    runs = json.loads(Path(f"results/phase4_{bench}/summary.json").read_text())["runs"]
    cells = sorted(runs, key=lambda r: (r["condition"], r["budget"], r["seed"]))
    print(f"== {bench} ({len(runs)})")
    by_budget = {}
    for c in cells:
        key = (c["condition"], c["budget"])
        by_budget.setdefault(key, []).append(c)
    for (cond, budget), rs in sorted(by_budget.items()):
        n = sum(1 for r in rs if r["success"])
        print(f"  {cond}@{budget}: {n}/{len(rs)}")