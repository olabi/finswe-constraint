"""FinSWE-Constraint harness — build, materialize, and score repository-level tasks.

Subcommands
-----------
build        Extract gold.patch / tests.patch from the source repo for each spec,
             then run the hidden tests at base and at base+gold to derive
             FAIL_TO_PASS / PASS_TO_PASS. A task is valid only if every
             FAIL_TO_PASS test fails at base and every hidden test passes with gold.
materialize  Write the buggy base snapshot of one task into a fresh git workdir
             (what the agent sees: no hidden tests, no CLAUDE.md / .claude/).
evaluate     Score a candidate patch against a task's hidden tests.

The source repo (ai-trader) is private; tasks reference its commits. A public
release will ship sanitized base snapshots instead of commit hashes.
"""

from __future__ import annotations

import argparse
import ast
import json
import os
import shutil
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TASKS = ROOT / "tasks"
DEFAULT_SOURCE = ROOT.parent / "ai-trader"
DEFAULT_PYTHON = DEFAULT_SOURCE / ".venv" / "bin" / "python"
# Public tasks (task.json has "repo") come from an open-source clone and its own venv,
# both set up by harness/public_task.py; they are never sanitized.
PUBLIC_ROOT = ROOT.parent / "public-src"


def source_for(spec: dict, src: Path) -> Path:
    return PUBLIC_ROOT / spec["repo"].rstrip("/").rsplit("/", 1)[1] if "repo" in spec else src


def python_for(spec: dict, python: Path) -> Path:
    return PUBLIC_ROOT / f"{spec['env']}-venv" / "bin" / "python" if "env" in spec else python

# Never shown to the agent: incident ledger / skills leak the fix and contain
# personal trading context.
EXCLUDE = ["CLAUDE.md", ".claude"]
CODE_PATHS = ["ai_trader/"]
TEST_PATHS = ["tests/"]


def sh(cmd: list[str], cwd: Path | None = None, check: bool = True, **kw) -> str:
    r = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, **kw)
    if check and r.returncode != 0:
        raise RuntimeError(f"{' '.join(cmd)}\n{r.stdout}\n{r.stderr}")
    return r.stdout


def git(src: Path, *args: str) -> str:
    return sh(["git", "-C", str(src), *args])


# ── public-release sanitizing ─────────────────────────────────────────────
LIVE_STUB = '''class LiveBrokerAdapter:
    """Removed from the FinSWE-Constraint snapshot: live order execution is out of scope."""

    def __init__(self, *args, **kwargs):
        raise RuntimeError("live trading is disabled in the FinSWE-Constraint snapshot")
'''


def _span(node: ast.AST) -> tuple[int, int]:
    start = min([node.lineno] + [d.lineno for d in getattr(node, "decorator_list", [])])
    return start - 1, node.end_lineno


ORDER_METHODS = ("orders", "order_get", "order_create", "order_cancel")
ORDER_MSG = "order API is disabled in the FinSWE-Constraint snapshot"
ORDER_GUARD = "# finswe: order endpoints disabled"
LIVE_TEST_MARKERS = ("LiveBrokerAdapter",) + tuple(f".{m}(" for m in ORDER_METHODS)


def _stub_order_api(client_py: Path) -> None:
    """TossClient order methods raise; _request refuses /api/v1/orders (defense in depth)."""
    text = client_py.read_text(encoding="utf-8")
    lines = text.splitlines(keepends=True)
    edits = []  # (start, end, replacement) on 0-based line ranges
    for cls in ast.parse(text).body:
        if not (isinstance(cls, ast.ClassDef) and cls.name == "TossClient"):
            continue
        for fn in cls.body:
            if not isinstance(fn, ast.FunctionDef) or not fn.body:
                continue
            first = fn.body[0]
            has_doc = (isinstance(first, ast.Expr) and isinstance(getattr(first, "value", None), ast.Constant)
                       and isinstance(first.value.value, str))
            pad = " " * first.col_offset
            if fn.name in ORDER_METHODS:
                keep_to = first.end_lineno if has_doc else first.lineno - 1
                edits.append((keep_to, fn.end_lineno, f'{pad}raise RuntimeError("{ORDER_MSG}")\n'))
            elif fn.name == "_request" and ORDER_GUARD not in text:
                at = first.end_lineno if has_doc else first.lineno - 1
                edits.append((at, at, f'{pad}{ORDER_GUARD}\n{pad}if path.startswith("/api/v1/orders"):\n'
                                      f'{pad}    raise RuntimeError("{ORDER_MSG}")\n'))
    for a, b, rep in sorted(edits, reverse=True):
        lines[a:b] = [rep]
    client_py.write_text("".join(lines), encoding="utf-8")


def sanitize(root: Path) -> None:
    """Strip the live-trading path (deterministic, idempotent).

    engine.LiveBrokerAdapter becomes a stub that raises; TossClient order methods
    (list/get/create/cancel) raise and _request refuses /api/v1/orders; top-level
    tests that use any of them are removed. Applied identically to base and to
    base+patch trees, so public patches are re-derived as the diff between two
    sanitized trees.
    """
    client = root / "ai_trader" / "client.py"
    if client.exists():
        _stub_order_api(client)
    eng = root / "ai_trader" / "engine.py"
    if eng.exists():
        text = eng.read_text(encoding="utf-8")
        lines = text.splitlines(keepends=True)
        for node in ast.parse(text).body:
            if isinstance(node, ast.ClassDef) and node.name == "LiveBrokerAdapter":
                a, b = _span(node)
                lines[a:b] = [LIVE_STUB]
                break
        eng.write_text("".join(lines), encoding="utf-8")
    for t in sorted((root / "tests").glob("*.py")) if (root / "tests").exists() else []:
        text = t.read_text(encoding="utf-8")
        lines = text.splitlines(keepends=True)
        drop = [_span(n) for n in ast.parse(text).body
                if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
                and any(m in "".join(lines[n.lineno - 1:n.end_lineno]) for m in LIVE_TEST_MARKERS)]
        for a, b in reversed(drop):
            del lines[a:b]
        if drop:
            t.write_text("".join(lines), encoding="utf-8")


# ── snapshot ──────────────────────────────────────────────────────────────
def materialize(spec: dict, task_dir: Path, src: Path, dest: Path, sanitized: bool = True) -> Path:
    """Buggy base snapshot as a fresh git repo with a single 'base' commit."""
    src = source_for(spec, src)
    if dest.exists():
        shutil.rmtree(dest)
    dest.mkdir(parents=True)
    archive = subprocess.run(
        ["git", "-C", str(src), "archive", spec["base"]], capture_output=True, check=True
    ).stdout
    subprocess.run(["tar", "-x", "-C", str(dest)], input=archive, check=True)
    for name in EXCLUDE:
        p = dest / name
        if p.is_dir():
            shutil.rmtree(p)
        elif p.exists():
            p.unlink()
    bug = task_dir / "bug.patch"  # reconstructed tasks: re-inject the bug
    if spec.get("bug_patch_withheld") and not bug.exists():
        # bug.patch reverses to the fix, so it is withheld from the public release with the gold
        # patches; without it this snapshot would have no bug.
        raise FileNotFoundError(f"{spec['id']}: bug.patch is withheld from the public release")
    if bug.exists():
        sh(["git", "apply", str(bug)], cwd=dest)
    if sanitized and "repo" not in spec:
        sanitize(dest)
    sh(["git", "init", "-q"], cwd=dest)
    sh(["git", "add", "-A"], cwd=dest)
    sh(["git", "-c", "user.name=finswe", "-c", "user.email=finswe@local",
        "commit", "-qm", "base"], cwd=dest)
    return dest


def public_patch(spec: dict, task_dir: Path, src: Path, raw: Path, sub: str) -> str:
    """Re-derive a raw patch (vs the unsanitized base) against the sanitized base."""
    with tempfile.TemporaryDirectory(prefix="finswe-pub-") as tmp:
        rawtree = materialize(spec, task_dir, src, Path(tmp) / "raw", sanitized=False)
        _apply(raw, rawtree)
        sanitize(rawtree)
        pub = materialize(spec, task_dir, src, Path(tmp) / "pub")
        shutil.rmtree(pub / sub, ignore_errors=True)
        shutil.copytree(rawtree / sub, pub / sub,
                        ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
        sh(["git", "add", "-A", "--", sub], cwd=pub)
        return sh(["git", "diff", "--cached", "--", sub], cwd=pub)


def _apply(patch: Path, cwd: Path) -> None:
    if patch.exists() and patch.read_text().strip():
        sh(["git", "apply", "--whitespace=nowarn", str(patch)], cwd=cwd)


def _patched_files(patch: Path) -> list[str]:
    files = []
    for line in patch.read_text().splitlines():
        if line.startswith("+++ b/"):
            files.append(line[6:])
    return files


def run_tests(work: Path, python: Path) -> dict[str, str]:
    """Run the full suite; return {nodeid: passed|failed|error|skipped}."""
    xml = work / ".finswe-junit.xml"
    subprocess.run(
        [str(python), "-m", "pytest", "-q", "-p", "no:cacheprovider",
         f"--junitxml={xml}", "tests"],
        cwd=work, capture_output=True, text=True,
        env={**os.environ, "PYTHONPATH": str(work), "PYTHONDONTWRITEBYTECODE": "1"},
    )
    out: dict[str, str] = {}
    if not xml.exists():
        return out
    for tc in ET.parse(xml).getroot().iter("testcase"):
        cls = tc.get("classname", "").replace(".", "/")
        nodeid = f"{cls}.py::{tc.get('name')}"
        status = "passed"
        for child in tc:
            if child.tag in ("failure", "error"):
                status = "failed"
            elif child.tag == "skipped":
                status = "skipped"
        out[nodeid] = status
    xml.unlink()
    return out


def score(spec: dict, task_dir: Path, src: Path, python: Path, candidate: Path | None) -> dict:
    """Apply candidate (None = no change) + hidden tests, return pass/fail per test."""
    with tempfile.TemporaryDirectory(prefix="finswe-") as tmp:
        work = materialize(spec, task_dir, src, Path(tmp) / "repo")
        if candidate is not None:
            _apply(candidate, work)
        tests = task_dir / "tests.public.patch"
        # Hidden tests replace whatever the agent did to those files.
        for f in _patched_files(tests):
            if (work / f).exists():
                subprocess.run(["git", "checkout", "base", "--", f], cwd=work,
                               capture_output=True)
        _apply(tests, work)
        return run_tests(work, python)


# ── build ─────────────────────────────────────────────────────────────────
def build(spec: dict, task_dir: Path, src: Path, python: Path) -> dict:
    if not spec.get("handwritten"):
        base, fix = spec["base"], spec["fix"]
        (task_dir / "gold.patch").write_text(git(src, "diff", base, fix, "--", *CODE_PATHS))
        # tests.orig.patch = the commit's own tests (provenance). tests.patch = scored
        # version; hand-relaxed copies (wording-coupled asserts removed) are kept.
        orig = git(src, "diff", base, fix, "--", *TEST_PATHS)
        (task_dir / "tests.orig.patch").write_text(orig)
        if not (task_dir / "tests.patch").exists():
            (task_dir / "tests.patch").write_text(orig)
    # raw patches (vs the unsanitized base) are provenance; *.public.patch are what
    # snapshots, scoring, verifier selftests and the Kaggle export use.
    (task_dir / "gold.public.patch").write_text(
        public_patch(spec, task_dir, src, task_dir / "gold.patch", "ai_trader"))
    (task_dir / "tests.public.patch").write_text(
        public_patch(spec, task_dir, src, task_dir / "tests.patch", "tests"))
    at_base = score(spec, task_dir, src, python, None)
    at_gold = score(spec, task_dir, src, python, task_dir / "gold.public.patch")
    f2p = sorted(t for t, s in at_gold.items() if s == "passed" and at_base.get(t) != "passed")
    p2p = sorted(t for t, s in at_gold.items() if s == "passed" and at_base.get(t) == "passed")
    broken = sorted(t for t, s in at_gold.items() if s != "passed")
    meta = {
        "FAIL_TO_PASS": f2p,
        "PASS_TO_PASS": p2p,
        "gold_failures": broken,
        "valid": bool(f2p) and not broken,
    }
    (task_dir / "eval.json").write_text(json.dumps(meta, indent=2, ensure_ascii=False) + "\n")
    return meta


def evaluate(spec: dict, task_dir: Path, src: Path, python: Path, candidate: Path) -> dict:
    meta = json.loads((task_dir / "eval.json").read_text())
    res = score(spec, task_dir, src, python, candidate)
    f2p_ok = [t for t in meta["FAIL_TO_PASS"] if res.get(t) == "passed"]
    p2p_ok = [t for t in meta["PASS_TO_PASS"] if res.get(t) == "passed"]
    return {
        "task": spec["id"],
        "resolved": len(f2p_ok) == len(meta["FAIL_TO_PASS"])
        and len(p2p_ok) == len(meta["PASS_TO_PASS"]),
        "f2p": f"{len(f2p_ok)}/{len(meta['FAIL_TO_PASS'])}",
        "p2p": f"{len(p2p_ok)}/{len(meta['PASS_TO_PASS'])}",
        "f2p_failed": sorted(set(meta["FAIL_TO_PASS"]) - set(f2p_ok)),
        "p2p_failed": sorted(set(meta["PASS_TO_PASS"]) - set(p2p_ok)),
    }


def load_specs(only: list[str] | None) -> list[tuple[dict, Path]]:
    out = []
    for d in sorted(TASKS.iterdir()):
        f = d / "task.json"
        if f.exists():
            spec = json.loads(f.read_text())
            if not only or spec["id"] in only:
                out.append((spec, d))
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("cmd", choices=["build", "materialize", "evaluate"])
    ap.add_argument("--task", action="append", help="task id (repeatable; default all)")
    ap.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    ap.add_argument("--python", type=Path, default=DEFAULT_PYTHON)
    ap.add_argument("--dest", type=Path, help="materialize: output directory")
    ap.add_argument("--patch", type=Path, help="evaluate: candidate patch")
    a = ap.parse_args()
    if a.patch is not None:
        a.patch = a.patch.resolve()

    specs = load_specs(a.task)
    if not specs:
        print("no tasks matched", file=sys.stderr)
        return 1
    if a.cmd == "build":
        ok = True
        for spec, d in specs:
            if "repo" in spec:  # public tasks: harness/public_task.py build
                print(f"{spec['id']:<28} skipped (public task — use public_task.py build)")
                continue
            m = build(spec, d, a.source, a.python)
            ok &= m["valid"]
            flag = "VALID" if m["valid"] else "INVALID"
            print(f"{spec['id']:<28} {flag:<8} F2P={len(m['FAIL_TO_PASS'])} "
                  f"P2P={len(m['PASS_TO_PASS'])} gold_fail={len(m['gold_failures'])}")
        return 0 if ok else 1
    if a.cmd == "materialize":
        spec, d = specs[0]
        dest = a.dest or Path(tempfile.mkdtemp(prefix=f"{spec['id']}-"))
        print(materialize(spec, d, a.source, dest))
        return 0
    spec, d = specs[0]
    print(json.dumps(evaluate(spec, d, a.source, python_for(spec, a.python), a.patch), indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
