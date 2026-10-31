"""Public FinSWE tasks (task.json has "repo"): set up the upstream clone and venv, then
build and validate the task the same way `finswe.py build` does for the private ones.

  public_task.py setup  [--task ID]   clone the repo into ../public-src/<name>, create
                                      ../public-src/<env>-venv and install the base commit
  public_task.py build  [--task ID]   run the hidden tests at base and at base+gold; write
                                      FAIL_TO_PASS / PASS_TO_PASS and valid into eval.json
  public_task.py wheels [--task ID]   download the venv's wheels to dist/<env>-wheels for an
                                      offline Kaggle kernel (upload as a private dataset)

A task is valid only if every FAIL_TO_PASS test fails at base and every hidden test passes
with gold. Then run `verify.py selftest --task ID` for the domain verifier.
Needs network (git clone, pip). Nothing here runs on Kaggle.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import finswe  # noqa: E402


def _public(ids: list[str] | None) -> list[tuple[dict, Path]]:
    return [(s, d) for s, d in finswe.load_specs(ids) if "repo" in s]


def setup(spec: dict, tdir: Path) -> None:
    src = finswe.source_for(spec, finswe.DEFAULT_SOURCE)
    if not (src / ".git").exists():
        src.parent.mkdir(parents=True, exist_ok=True)
        finswe.sh(["git", "clone", "-q", spec["repo"], str(src)])
    finswe.git(src, "cat-file", "-e", spec["base"])
    py = finswe.python_for(spec, finswe.DEFAULT_PYTHON)
    if not py.exists():
        finswe.sh([sys.executable, "-m", "venv", str(py.parents[1])])
    with tempfile.TemporaryDirectory(prefix="finswe-setup-") as tmp:
        work = finswe.materialize(spec, tdir, src, Path(tmp) / "base")
        finswe.sh([str(py), "-m", "pip", "install", "-q", f"{work}[dev]"])
    # dependencies only: the code under test always comes from the workdir (PYTHONPATH)
    finswe.sh([str(py), "-m", "pip", "uninstall", "-q", "-y", spec["pkg"]])
    print(f"{spec['id']}: {src} @ {spec['base'][:7]}, python {py}")


def build(spec: dict, tdir: Path) -> bool:
    src = finswe.source_for(spec, finswe.DEFAULT_SOURCE)
    py = finswe.python_for(spec, finswe.DEFAULT_PYTHON)
    tests = tdir / "tests.patch"
    with tempfile.TemporaryDirectory(prefix="finswe-build-") as tmp:
        base = finswe.materialize(spec, tdir, src, Path(tmp) / "base")
        finswe._apply(tests, base)
        at_base = finswe.run_tests(base, py)
        gold = finswe.materialize(spec, tdir, src, Path(tmp) / "gold")
        finswe._apply(tdir / "gold.patch", gold)
        finswe._apply(tests, gold)
        at_gold = finswe.run_tests(gold, py)
    hidden = [t for t in at_gold if t.startswith(finswe._patched_files(tests)[0])]
    meta = json.loads((tdir / "eval.json").read_text())
    f2p = meta["FAIL_TO_PASS"]
    p2p = sorted(t for t, s in at_gold.items() if s == "passed" and at_base.get(t) == "passed")
    gold_failures = sorted(t for t, s in at_gold.items() if s in ("failed", "error"))
    problems = [f"F2P passes at base: {t}" for t in f2p if at_base.get(t) == "passed"]
    problems += [f"hidden test not passing with gold: {t} ({at_gold.get(t)})"
                 for t in hidden + f2p if at_gold.get(t) != "passed"]
    meta.update(PASS_TO_PASS=p2p, gold_failures=gold_failures, valid=not problems)
    meta.pop("note", None)
    (tdir / "eval.json").write_text(json.dumps(meta, indent=2) + "\n")
    print(f"{spec['id']}: base {len(at_base)} tests, gold {len(at_gold)}; F2P {len(f2p)}, P2P {len(p2p)}, "
          f"gold failures {len(gold_failures)} → {'VALID' if not problems else 'INVALID'}")
    for p in problems:
        print("  ", p)
    return not problems


# Not needed by the task, but imported by the Kaggle image's sitecustomize at every interpreter
# start: without it the venv's python prints "Error in sitecustomize … No module named 'wrapt'"
# into every agent command (seen in kernel v10).
KAGGLE_IMAGE_EXTRAS = ("wrapt",)


def wheels(spec: dict, python_version: str) -> None:
    py = finswe.python_for(spec, finswe.DEFAULT_PYTHON)
    out = finswe.ROOT / "dist" / f"{spec['env']}-wheels"
    out.mkdir(parents=True, exist_ok=True)
    frozen = finswe.sh([str(py), "-m", "pip", "freeze", "--exclude-editable"])
    reqs = [line for line in frozen.splitlines() if line and not line.startswith(("-e", "tradingagents"))]
    pinned = {line.split("==")[0].lower() for line in reqs}
    reqs += [pkg for pkg in KAGGLE_IMAGE_EXTRAS if pkg.lower() not in pinned]
    (out / "requirements.txt").write_text("\n".join(reqs) + "\n")
    finswe.sh([str(py), "-m", "pip", "download", "-q", "-d", str(out), "--only-binary=:all:",
               "--python-version", python_version,
               # newer wheels (e.g. numpy 2.5) ship only manylinux_2_28; list every tag the image accepts
               *[a for tag in ("manylinux_2_28_x86_64", "manylinux_2_17_x86_64", "manylinux2014_x86_64")
                 for a in ("--platform", tag)],
               "-r", str(out / "requirements.txt")])
    (out / "dataset-metadata.json").write_text(json.dumps({
        "title": f"finswe-{spec['env']}-wheels", "id": f"kmmmvs/finswe-{spec['env']}-wheels",
        "licenses": [{"name": "other"}]}, indent=2))
    print(f"{len(list(out.glob('*.whl')))} wheels for Python {python_version} → {out}")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("cmd", choices=["setup", "build", "wheels"])
    ap.add_argument("--task", action="append")
    ap.add_argument("--python-version", default="3.11", help="the Kaggle image's Python (wheels only)")
    a = ap.parse_args()
    ok = True
    for spec, tdir in _public(a.task):
        if a.cmd == "setup":
            setup(spec, tdir)
        elif a.cmd == "build":
            ok &= build(spec, tdir)
        else:
            wheels(spec, a.python_version)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
