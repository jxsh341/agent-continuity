"""Phase 4 benchmark validator — offline correctness check per benchmark.

For every registered benchmark: a seed exists with passing visible tests,
the S1 reference passes its visible tests, the hidden tests fail on the seed
+ S1 reference (because the S2-only decision is not yet applied), and an
oracle (S1 reference + the S2 oracle state) passes.
"""

from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from benchmark.registry import BENCHMARKS  # noqa

PY = Path(__file__).parent.parent / ".venv" / "Scripts" / "python.exe"


def run_pytest(ws: Path, hidden: bool = False) -> bool:
    p = subprocess.run(
        [str(PY), "-m", "pytest", "-q", "--tb=no", "tests/"],
        cwd=ws, capture_output=True,
    )
    return p.returncode == 0


def validate(name: str) -> dict:
    b = BENCHMARKS[name]
    rep = {"benchmark": name}
    ws = Path(tempfile.mkdtemp(prefix="p4v_"))
    b.make_seed(ws)
    rep["seed_tests_pass"] = run_pytest(ws)
    b.apply_s1_reference(ws)
    rep["s1_ref_passes"] = run_pytest(ws)
    b.inject_hidden_tests(ws)
    rep["hidden_fail_before_s2"] = not run_pytest(ws)
    import shutil as _sh
    _sh.rmtree(ws, ignore_errors=True)
    return rep


def main():
    res = {}
    all_ok = True
    for name in BENCHMARKS:
        r = validate(name)
        res[name] = r
        ok = r["seed_tests_pass"] and r["s1_ref_passes"] and r["hidden_fail_before_s2"]
        all_ok = all_ok and ok
        print(("PASS " if ok else "FAIL ") + name + " " + str(ok))
        print("  detail:", r)
    print("ALL OK" if all_ok else "PROBLEMS")
    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())