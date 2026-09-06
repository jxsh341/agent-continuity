"""Offline validation of the Stage 1 benchmarks (no LLM, no endpoint).

Per benchmark: seed is valid Python repo; visible tests pass on seed;
oracle passes hidden tests; hidden tests FAIL on a pristine seed (so the
benchmark really requires memory of S1 design); contamination scanner
works; CRITICAL_FACTS table present.
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from benchmark.registry import BENCHMARKS  # noqa: E402

PY = Path(__file__).parent.parent / ".venv" / "Scripts" / "python.exe"


def run_pytest(ws: Path) -> bool:
    return subprocess.run(
        [str(PY), "-m", "pytest", "-q", "--tb=no", "tests/"],
        cwd=ws, capture_output=True,
    ).returncode == 0


def validate(name: str) -> dict:
    b = BENCHMARKS[name]
    report = {"benchmark": name}

    r = {"seed_dir": tempfile.mkdtemp(prefix=f"val_{name}_")}
    ws = Path(r["seed_dir"])
    b.make_seed(ws)

    report["seed_visible_tests_pass"] = run_pytest(ws)
    b.inject_hidden_tests(ws)
    report["hidden_fail_on_seed"] = not run_pytest(ws)

    ws2 = Path(tempfile.mkdtemp(prefix=f"val_{name}_oracle_"))
    b.make_seed(ws2)
    b.apply_oracle(ws2)
    b.inject_hidden_tests(ws2)
    report["oracle_passes_full_suite"] = run_pytest(ws2)

    report["facts_defined"] = len(b.CRITICAL_FACTS) >= 3
    fake_ctx = " ".join(f["label"] for f in b.CRITICAL_FACTS)
    report["fact_checks_fire"] = all(f["check"](fake_ctx) for f in b.CRITICAL_FACTS)

    import shutil
    shutil.rmtree(ws, ignore_errors=True)
    shutil.rmtree(ws2, ignore_errors=True)
    return report


def main() -> int:
    results = {}
    for name in BENCHMARKS:
        r = validate(name)
        results[name] = r
        ok = all(v for k, v in r.items() if k != "benchmark")
        print(("PASS " if ok else "FAIL "), name, json.dumps(r))
    return 0 if all(
        all(v for k, v in r.items() if k != "benchmark")
        for r in results.values()
    ) else 1


if __name__ == "__main__":
    sys.exit(main())
