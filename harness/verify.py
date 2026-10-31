"""Feedback verifiers — what the agent is told after each patch attempt.

Levels (experimental conditions):
  generic  G-SYNTAX, G-HYGIENE, G-REGRESSION (repo's own visible tests)   → condition B
  domain   per-task invariant checks (harness/verifiers/domain/<task>.py) → added in C
  all      generic, then domain                                          → condition C

Feedback is disjoint from scoring: hidden tests (tasks/<id>/tests.patch) are never
run here, and domain checks use their own symbols, price paths and thresholds.

Usage:
  verify.py check --task FSC-001-core-guard --workdir W [--level all] [--json]
  verify.py selftest [--task ID ...]   # each domain verifier must FAIL at base, PASS at gold
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import finswe  # noqa: E402
from feedback import VERIFIERS, check, render  # noqa: E402,F401

# ── selftest ──────────────────────────────────────────────────────────────
def selftest(ids: list[str] | None, src: Path, python: Path) -> bool:
    ok_all = True
    for spec, tdir in finswe.load_specs(ids):
        tid = spec["id"]
        if not (tdir / "gold.public.patch").exists():
            # Core-task gold patches are withheld from the public release (they are the answers);
            # the selftest then needs the private source and a private copy of tasks/.
            print(f"{tid:<28} SKIP gold withheld from the public release")
            continue
        py = finswe.python_for(spec, python)
        with tempfile.TemporaryDirectory(prefix="fsc-self-") as tmp:
            base = finswe.materialize(spec, tdir, src, Path(tmp) / "base")
            gold = finswe.materialize(spec, tdir, src, Path(tmp) / "gold")
            subprocess.run(["git", "apply", str(tdir / "gold.public.patch")], cwd=gold, check=True)
            rb = check(tid, base, py, "domain")["results"]
            rg = check(tid, gold, py, "all")["results"]
        base_flags = [r["id"] for r in rb if r["status"] != "pass"]
        gold_bad = [f"{r['id']}:{r['status']}:{r['observed'][:90]}" for r in rg
                    if r["status"] != "pass"]
        control = spec.get("family") == "control"  # no domain invariant by design
        good = (not rb if control else bool(base_flags)) and not gold_bad
        ok_all &= good
        print(f"{tid:<28} {'OK ' if good else 'BAD'} base-flags={len(base_flags)}/{len(rb)} "
              f"{base_flags}  gold={'clean' if not gold_bad else gold_bad}")
    return ok_all


def main() -> int:
    ap = argparse.ArgumentParser(description="FinSWE-Constraint feedback verifiers")
    ap.add_argument("cmd", choices=["check", "selftest"])
    ap.add_argument("--task", action="append")
    ap.add_argument("--workdir", type=Path)
    ap.add_argument("--level", choices=["generic", "domain", "all"], default="all")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--source", type=Path, default=finswe.DEFAULT_SOURCE)
    ap.add_argument("--python", type=Path, default=finswe.DEFAULT_PYTHON)
    a = ap.parse_args()
    if a.cmd == "selftest":
        return 0 if selftest(a.task, a.source, a.python) else 1
    rep = check(a.task[0], a.workdir, a.python, a.level)
    print(json.dumps(rep, indent=2, ensure_ascii=False) if a.json else render(rep))
    return 0 if rep["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
