"""Feedback verifiers (shared by verify.py locally and the Kaggle pilot runner).

Levels = experimental conditions:
  generic  G-SYNTAX, G-HYGIENE, G-REGRESSION (repo's own visible tests)   → condition B
  domain   per-task invariant checks (verifiers/domain/<FSC-nnn>.py)      → added in C
  all      generic, then domain                                          → condition C

Hidden scoring tests are never run here; domain checks use their own scenarios.
No dependency on the private source repo: works on any materialized workdir whose
first commit is the task base.
"""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent
VERIFIERS = HERE / "verifiers"
MAX_REGRESSION_LINES = 12


def _spec(task_id: str) -> dict:
    """task.json next to this harness (repo checkout or exported dataset); {} if absent."""
    f = HERE.parent / "tasks" / task_id / "task.json"
    return json.loads(f.read_text()) if f.exists() else {}


def _code_dirs(task_id: str) -> tuple[str, ...]:
    return tuple(_spec(task_id).get("code_dirs", ["ai_trader/", "tests/"]))


def _git(work: Path, *args: str) -> str:
    return subprocess.run(["git", *args], cwd=work, capture_output=True, text=True).stdout


def _base_sha(work: Path) -> str:
    return _git(work, "rev-list", "--max-parents=0", "HEAD").strip()


def _changed(work: Path) -> tuple[list[str], list[str]]:
    """(existing files modified/deleted vs base, files new since base).

    New files are classified by existence at base, not by git index state:
    submit_patch runs `git add -N .` first, which turns untracked files into
    intent-to-add entries, and they must still count as new.
    """
    base = _base_sha(work)
    at_base = set(_git(work, "ls-tree", "-r", "--name-only", base).splitlines())
    tracked = [f for f in _git(work, "diff", "--name-only", base).splitlines() if f]
    untracked = [f for f in _git(work, "ls-files", "--others", "--exclude-standard").splitlines()
                 if f and "__pycache__" not in f and not f.startswith(".pytest_cache")]
    modified = [f for f in tracked if f in at_base]
    new = sorted({f for f in tracked if f not in at_base} | set(untracked))
    return modified, new


def _result(cid, title, status, expected, observed="", scenario=""):
    return {"id": cid, "title": title, "status": status, "scenario": scenario,
            "expected": expected, "observed": observed}


# ── generic level ─────────────────────────────────────────────────────────
def generic(work: Path, python: Path, code_dirs: tuple[str, ...] = ("ai_trader/", "tests/")) -> list[dict]:
    out = []
    modified, untracked = _changed(work)
    py = [f for f in modified + untracked if f.endswith(".py") and (work / f).exists()]

    errs = []
    for f in py:
        try:
            compile((work / f).read_bytes(), f, "exec")
        except SyntaxError as e:
            errs.append(f"{f}:{e.lineno}: {e.msg}")
    out.append(_result("G-SYNTAX", "changed Python files compile",
                       "fail" if errs else "pass", "every changed .py compiles",
                       "; ".join(errs)))

    issues = []
    if not modified and not untracked:
        issues.append("empty patch — no file differs from base")
    issues += [f"existing test modified: {f}" for f in modified if f.startswith("tests/")]
    issues += [f"stray new file outside {' and '.join(code_dirs)} (delete it with `rm`; scratch files belong in /tmp, "
               f"written via run_command): {f}"
               for f in untracked if not f.startswith(code_dirs)]
    out.append(_result("G-HYGIENE", "patch hygiene", "fail" if issues else "pass",
                       "non-empty patch; existing tests untouched; no scratch files",
                       "; ".join(issues)))

    if errs:
        out.append(_result("G-REGRESSION", "visible test suite", "error",
                           "all visible tests pass", "skipped: syntax errors first"))
        return out
    now = _junit(work, python)
    base_fail = _baseline_failures(work, python)
    new_fail = {t: m for t, m in now.items() if m is not None and t not in base_fail}
    ignored = sorted(t for t in base_fail if t in now)
    note = (f"\n({len(ignored)} test(s) already failing at base in this environment were ignored: "
            + ", ".join(ignored[:3]) + ")") if ignored else ""
    if not now:
        out.append(_result("G-REGRESSION", "visible test suite", "error",
                           "visible tests run", "pytest produced no results (collection error?)"))
    else:
        lines = [f"FAILED {t} - {m}" for t, m in list(new_fail.items())[:MAX_REGRESSION_LINES]]
        passed = sum(m is None for m in now.values())
        out.append(_result(
            "G-REGRESSION", "visible test suite (regressions vs base)",
            "fail" if new_fail else "pass",
            "no visible test that passes at base fails after the patch",
            ("\n".join(lines + [f"{len(new_fail)} new failure(s), {passed} passed"]) + note)
            if new_fail else ""))
    return out


def _junit(work: Path, python: Path) -> dict[str, str | None]:
    """Run the visible suite; {nodeid: None if passed else short failure message}."""
    import tempfile
    import xml.etree.ElementTree as ET

    with tempfile.NamedTemporaryFile(suffix=".xml", delete=False) as f:
        xml = Path(f.name)
    subprocess.run(
        [str(python), "-m", "pytest", "-q", "-p", "no:cacheprovider", f"--junitxml={xml}", "tests"],
        cwd=work, capture_output=True, text=True,
        env={**os.environ, "PYTHONPATH": str(work), "PYTHONDONTWRITEBYTECODE": "1"},
    )
    out: dict[str, str | None] = {}
    try:
        root = ET.parse(xml).getroot()
    except (ET.ParseError, FileNotFoundError):
        return out
    finally:
        xml.unlink(missing_ok=True)
    for tc in root.iter("testcase"):
        nodeid = f"{tc.get('classname', '').replace('.', '/')}.py::{tc.get('name')}"
        msg = None
        for ch in tc:
            if ch.tag in ("failure", "error"):
                msg = (ch.get("message") or ch.tag).splitlines()[0][:160]
        out[nodeid] = msg
    return out


_BASELINE: dict[tuple[str, str], set[str]] = {}


def _baseline_failures(work: Path, python: Path) -> set[str]:
    """Visible tests that already fail at the base commit *in this environment* (cached).

    A regression is a test that passed at base and fails after the patch; tests that
    cannot pass here at all (e.g. an optional dependency missing offline) are not.
    """
    import tempfile

    key = (_base_sha(work), str(python))
    if key not in _BASELINE:
        with tempfile.TemporaryDirectory(prefix="fsc-base-") as tmp:
            arch = subprocess.run(["git", "-C", str(work), "archive", key[0]], capture_output=True)
            subprocess.run(["tar", "-x", "-C", tmp], input=arch.stdout, check=True)
            res = _junit(Path(tmp), python)
        _BASELINE[key] = {t for t, m in res.items() if m is not None}
    return _BASELINE[key]


# ── domain level ──────────────────────────────────────────────────────────
def _domain_script(task_id: str) -> Path:
    return VERIFIERS / "domain" / f"{task_id.split('-')[0]}-{task_id.split('-')[1]}.py"


def describe(task_id: str, work: Path, python: Path) -> list[dict]:
    """The domain invariants a task's verifier checks (id/title/scenario/expected), without
    running them. Used to give the A_know / C_know conditions the same knowledge the
    domain gate encodes."""
    script = _domain_script(task_id)
    if not script.exists():
        return []
    r = subprocess.run(
        [str(python), str(script), str(VERIFIERS)], cwd=work, capture_output=True, text=True,
        env={**os.environ, "PYTHONPATH": str(work), "PYTHONDONTWRITEBYTECODE": "1",
             "FINSWE_PKG": _spec(task_id).get("pkg", "ai_trader"), "FINSWE_DESCRIBE": "1"}, timeout=120,
    )
    line = next((l for l in r.stdout.splitlines() if l.startswith("FINSWE_DESCRIBE ")), None)
    if line is None:
        raise RuntimeError(f"{task_id}: describe failed: {(r.stderr.strip().splitlines() or ['?'])[-1]}")
    return json.loads(line[len("FINSWE_DESCRIBE "):])


def domain(task_id: str, work: Path, python: Path) -> tuple[list[dict], str]:
    script = _domain_script(task_id)
    if not script.exists():
        return [], ""
    r = subprocess.run(
        [str(python), str(script), str(VERIFIERS)], cwd=work, capture_output=True, text=True,
        env={**os.environ, "PYTHONPATH": str(work), "PYTHONDONTWRITEBYTECODE": "1",
             "FINSWE_PKG": _spec(task_id).get("pkg", "ai_trader")},
        timeout=300,
    )
    line = next((l for l in r.stdout.splitlines() if l.startswith("FINSWE_RESULTS ")), None)
    if line is None:  # import-time crash in agent code
        err = (r.stderr.strip().splitlines() or ["no output"])[-1]
        return [_result("D-IMPORT", "domain verifier could not load the package", "error",
                        "package imports cleanly", err)], ""
    payload = json.loads(line[len("FINSWE_RESULTS "):])
    return payload["checks"], payload["module"]


def check(task_id: str, work: Path, python: Path, level: str) -> dict:
    results, module = [], ""
    if level in ("generic", "all"):
        results += generic(work, python, _code_dirs(task_id))
    if level in ("domain", "all"):
        d, module = domain(task_id, work, python)
        results += d
    if module and not Path(module).resolve().is_relative_to(work.resolve()):
        raise RuntimeError(f"domain verifier imported {module}, not the agent's workdir {work}")
    return {"task": task_id, "level": level, "passed": all(r["status"] == "pass" for r in results),
            "results": results}


def render(report: dict) -> str:
    """Structured feedback text handed back to the agent."""
    bad = [r for r in report["results"] if r["status"] != "pass"]
    if not bad:
        return f"VERIFIER ({report['level']}): all {len(report['results'])} checks passed."
    lines = [f"VERIFIER ({report['level']}): {len(bad)} of {len(report['results'])} checks failed."]
    for r in bad:
        lines.append(f"\n[{r['status'].upper()}] {r['id']} — {r['title']}")
        if r["scenario"]:
            lines.append(f"  scenario: {r['scenario']}")
        lines.append(f"  expected: {r['expected']}")
        if r["observed"]:
            obs = r["observed"].replace("\n", "\n            ")
            lines.append(f"  observed: {obs}")
    return "\n".join(lines)


