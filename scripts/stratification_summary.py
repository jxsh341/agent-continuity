"""Summarize the extractor stratification results into summary tables.

Reads results/extractor_stratification/trials.jsonl and prints RQ1-RQ5 answers.
"""

import json
from collections import defaultdict

rows = [json.loads(l) for l in open("results/extractor_stratification/trials.jsonl")]

print("=== RQ1/RQ2: parse + schema reliability by TOKEN bin ===")
tok_bins = ["0-1500 tok", "1501-3000 tok", "3001-5000 tok", "5001-100000 tok"]
for b in tok_bins:
    d = [r for r in rows if r["tok_bin"] == b]
    if not d:
        continue
    parse = sum(1 for r in d if r["parse_success"])
    schema = sum(1 for r in d if r.get("schema_valid"))
    print(f"  {b:18} n={len(d):3}  parse={parse}/{len(d)}  "
          f"schema={schema}/{len(d)}")

print("\n=== RQ1/RQ2: by MESSAGE bin ===")
for b in ["0-20 msgs", "21-40 msgs", "41-60 msgs", "61-1000 msgs"]:
    d = [r for r in rows if r["msg_bin"] == b]
    if not d:
        continue
    parse = sum(1 for r in d if r["parse_success"])
    print(f"  {b:14} n={len(d):3}  parse={parse}/{len(d)}")

print("\n=== per-benchmark parse rate ===")
for bench in ["fastapi", "schema_migration", "config_env"]:
    br = [r for r in rows if r["benchmark"] == bench]
    p = sum(1 for r in br if r["parse_success"])
    print(f"  {bench:18} parse={p}/{len(br)} ({p/len(br):.0%})")

print("\n=== RQ3: fidelity among parse-success trials (config_env decomposition) ===")
for bench in ["fastapi", "schema_migration", "config_env"]:
    br = [r for r in rows if r["benchmark"] == bench and r["parse_success"]]
    if not br:
        print(f"  {bench}: no parse-success trials")
        continue
    # exact identifiers recall (any exact token present)
    exact_any = sum(
        1 for r in br
        if r.get("fidelity") and any(r["fidelity"]["exact_identifiers"].values())
    )
    # all exact present
    exact_all = sum(
        1 for r in br
        if r.get("fidelity") and all(r["fidelity"]["exact_identifiers"].values())
    )
    print(f"  {bench}: parsed={len(br)}  any_exact={exact_any}  all_exact={exact_all}")

print("\n=== RQ4: config_env key/value omission (parse-success only) ===")
ce = [r for r in rows if r["benchmark"] == "config_env" and r["parse_success"]]
env_ok = sum(1 for r in ce if r["fidelity"]["exact_identifiers"]["SHOPAPI_RATE_LIMIT_RPS"])
key_ok = sum(1 for r in ce if r["fidelity"]["exact_identifiers"]["rate_limit_rps"])
val_ok = sum(1 for r in ce if r["fidelity"]["exact_value"])
print(f"  env_var={env_ok}/{len(ce)}  config_key={key_ok}/{len(ce)}  value42={val_ok}/{len(ce)}")

print("\n=== RQ4: omission vs transcript length (config_env) ===")
for b in tok_bins:
    d = [r for r in ce if r["tok_bin"] == b]
    if not d:
        continue
    key_ok = sum(1 for r in d if r["fidelity"]["exact_identifiers"]["rate_limit_rps"])
    print(f"  {b:18} n={len(d):2} key_present={key_ok}/{len(d)}")