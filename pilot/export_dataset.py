"""Build the private Kaggle dataset folder for the pilot notebook.

  dist/finswe-pilot-data/
    snapshots/<id>.tgz        buggy base workspace (no .git, no CLAUDE.md/.claude)
    tasks/<id>/task.json      metadata (no gold/fix commit hashes needed at run time)
    tasks/<id>/issue.md       what the agent sees
    tasks/<id>/eval.json      FAIL_TO_PASS / PASS_TO_PASS
    tasks/<id>/hidden.b64     hidden tests, zlib+base64 (not grep-able)
    harness/feedback.py, harness/verifiers/**   gate verifiers
    pilot/finswe_pilot.py, pilot/system.md      runner + prompt

Gold patches are NOT shipped: gold sanity is checked locally before export, so the
agent sandbox (which can read /kaggle/input) never has the answer next to it.
Refuses to export if any snapshot file matches a secret pattern.
"""

from __future__ import annotations

import base64
import json
import re
import shutil
import sys
import tarfile
import tempfile
import zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "harness"))
import finswe  # noqa: E402

OUT = ROOT / "dist" / "finswe-pilot-data"
KAGGLE_USER = "kmmmvs"  # dataset owner; `kaggle datasets create` keeps it private by default
SECRET = re.compile(
    r"(sk-ant-[A-Za-z0-9_-]{10,}|sk-[A-Za-z0-9]{20,}|AKIA[0-9A-Z]{16}|"
    r"(?i:(app[_-]?secret|client[_-]?secret|api[_-]?key|password|passwd|token)\s*[=:]\s*['\"][^'\"\s]{12,}['\"]))")
ALLOWLIST_VALUES = {"sec-test", "cid-test", "verifier"}


def scan(dirpath: Path) -> list[str]:
    hits = []
    for p in dirpath.rglob("*"):
        if p.is_file() and p.suffix in {".py", ".md", ".txt", ".toml", ".json", ".example", ".cfg", ".ini", ""}:
            for m in SECRET.finditer(p.read_text(encoding="utf-8", errors="ignore")):
                if not any(v in m.group(0) for v in ALLOWLIST_VALUES):
                    hits.append(f"{p.relative_to(dirpath)}: {m.group(0)[:40]}…")
    return hits


def main() -> int:
    if OUT.exists():
        shutil.rmtree(OUT)
    (OUT / "snapshots").mkdir(parents=True)
    problems = []
    for spec, tdir in finswe.load_specs(None):
        tid = spec["id"]
        meta = json.loads((tdir / "eval.json").read_text())
        if not meta.get("valid"):
            problems.append(f"{tid}: eval.json not valid — run `finswe.py build` first")
            continue
        with tempfile.TemporaryDirectory() as tmp:
            work = finswe.materialize(spec, tdir, finswe.DEFAULT_SOURCE, Path(tmp) / "w")
            shutil.rmtree(work / ".git")
            hits = scan(work)
            if hits:
                problems += [f"{tid}: {h}" for h in hits]
                continue
            with tarfile.open(OUT / "snapshots" / f"{tid}.tgz", "w:gz") as tf:
                for p in sorted(work.rglob("*")):
                    tf.add(p, arcname=str(p.relative_to(work)), recursive=False)
        d = OUT / "tasks" / tid
        d.mkdir(parents=True)
        public = {k: spec[k] for k in ("id", "label", "family", "provenance", "invariant", "pkg", "code_dirs",
                                       "env", "repo_name") if k in spec}
        (d / "task.json").write_text(json.dumps(public, indent=2, ensure_ascii=False))
        shutil.copy(tdir / "issue.md", d / "issue.md")
        shutil.copy(tdir / "eval.json", d / "eval.json")
        (d / "hidden.b64").write_bytes(base64.b64encode(zlib.compress((tdir / "tests.public.patch").read_bytes())))
    if problems:
        print("EXPORT REFUSED:\n  " + "\n  ".join(problems))
        shutil.rmtree(OUT)
        return 1
    shutil.copytree(ROOT / "harness" / "verifiers", OUT / "harness" / "verifiers",
                    ignore=shutil.ignore_patterns("__pycache__"))
    shutil.copy(ROOT / "harness" / "feedback.py", OUT / "harness" / "feedback.py")
    (OUT / "pilot").mkdir()
    for f in ("finswe_pilot.py", "system.md", "analyze.py"):
        shutil.copy(ROOT / "pilot" / f, OUT / "pilot" / f)
    # private-dataset fallback only (Kaggle uses the installed swegemma, and the notebook asserts
    # edit_engine == "swegemma"); never in a public release. Optional: skipped when absent.
    if (ROOT / "pilot" / "_vendor").is_dir():
        shutil.copytree(ROOT / "pilot" / "_vendor", OUT / "pilot" / "_vendor",
                        ignore=shutil.ignore_patterns("__pycache__"))
    else:
        print("note: pilot/_vendor absent — exported without the local edit-engine fallback")
    (OUT / "dataset-metadata.json").write_text(json.dumps({
        "title": "finswe-pilot-data", "id": f"{KAGGLE_USER}/finswe-pilot-data",
        "licenses": [{"name": "other"}]}, indent=2))
    n = len(list((OUT / "tasks").iterdir()))
    size = sum(p.stat().st_size for p in OUT.rglob("*") if p.is_file())
    print(f"exported {n} tasks → {OUT} ({size / 1024:.0f} KiB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
