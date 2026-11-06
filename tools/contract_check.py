"""Check the repository against AGENTS.md (the contract). Stdlib only.

  python3 tools/contract_check.py                  # C1–C5 on the working tree / index
  python3 tools/contract_check.py --pr-body-env PR_BODY   # also C7: signed, fully ticked checklist
  python3 tools/contract_check.py --pr-title-env PR_TITLE --commit-range BASE..HEAD   # also C9: names
  python3 tools/contract_check.py --version        # print the signature line for a PR body

Exit status 0 only if every checked clause holds. Used by the CI job `contract` and by the
Claude Code hook .claude/hooks/contract_gate.py before every commit and push.
"""

from __future__ import annotations

import argparse
import fnmatch
import hashlib
import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# C1: files that solve a core task. FinSWE-21 (tasks/PUB-*) may ship its upstream gold.
ANSWERS = ["tasks/FSC-*/gold*.patch", "tasks/INJ-*/gold*.patch", "tasks/*/bug.patch",
           "*traces.zip", "harness/make_injected.py"]
# C2: paths we never publish.
FORBIDDEN = [".env*", "*/.env*", "pilot/_vendor/*", "*harness_src/*", "data/*_news.json", "data/*/*_news.json"]
SECRET = re.compile(
    r"(sk-ant-[A-Za-z0-9_-]{10,}|sk-[A-Za-z0-9]{20,}|AKIA[0-9A-Z]{16}|ghp_[A-Za-z0-9]{30,}|"
    r"(?i:(app[_-]?secret|client[_-]?secret|api[_-]?key|password|passwd|token)\s*[=:]\s*['\"][^'\"\s]{12,}['\"]))")
SECRET_ALLOW = ("sec-test", "cid-test", "verifier")
MARKERS = re.compile(r"\[(REV|TODO|VERIFY|KAGGLE)\b")
SUBTITLE_MAX = 140
CLAUSES = [f"C{i}" for i in range(1, 10)]
# C9: naming standard (AGENTS.md §2)
AREA = r"(PAPER|REPRO|RESULTS|HARNESS|TASKS|PILOT|DATA|CONTRACT|(FSC|INJ|PUB)-[A-Z0-9]+(-[a-z0-9-]+)?)"
TITLE_RE = re.compile(rf"^\[{AREA}\] \S")
COMMIT_RE = re.compile(rf"^(feat|fix|refactor|test|docs|chore): {AREA} \S")


def signature() -> str:
    return hashlib.sha256((ROOT / "AGENTS.md").read_bytes()).hexdigest()[:8]


def tracked() -> list[str]:
    out = subprocess.run(["git", "-C", str(ROOT), "ls-files", "-z"], capture_output=True, text=True, check=True)
    return [p for p in out.stdout.split("\0") if p and (ROOT / p).exists()]


def matches(path: str, patterns) -> bool:
    return any(fnmatch.fnmatch(path, pat) for pat in patterns)


def c1(files):
    return [f"C1 answer file in the repository: {f}" for f in files if matches(f, ANSWERS)]


def c2(files):
    bad = [f"C2 forbidden path: {f}" for f in files if matches(f, FORBIDDEN)]
    for f in files:
        p = ROOT / f
        if p.suffix in {".zip", ".png", ".svg", ".tgz", ".gz"} or p.stat().st_size > 5_000_000:
            continue
        try:
            text = p.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        for m in SECRET.finditer(text):
            if not any(v in m.group(0) for v in SECRET_ALLOW):
                bad.append(f"C2 secret-like string in {f}: {m.group(0)[:24]}…")
    return bad


def c3():
    r = subprocess.run([sys.executable, str(ROOT / "repro" / "reproduce.py")], cwd=ROOT,
                       capture_output=True, text=True)
    if r.returncode == 0:
        return []
    tail = [ln for ln in r.stdout.splitlines() if "✗" in ln or "MISMATCH" in ln][:8]
    return ["C3 repro/reproduce.py does not match the paper: " + (" | ".join(tail) or r.stderr[-300:])]


def _row(text: str, label: str) -> list[float] | None:
    """Numbers in the first markdown table row whose first cell is `label` (bold allowed)."""
    for line in text.splitlines():
        cells = [c.strip().strip("*") for c in line.strip().strip("|").split("|")]
        if len(cells) > 1 and cells[0] == label:
            return [float(m) for c in cells[1:] for m in re.findall(r"[+-]?\d+(?:\.\d+)?", c.replace("−", "-"))]
    return None


def c3_paper():
    """The paper's own tables agree with repro/expected.json, which reproduce.py checks against the records."""
    import json
    exp = json.loads((ROOT / "repro" / "expected.json").read_text())
    text = (ROOT / "paper" / "writeup.md").read_text(encoding="utf-8")
    arms = ["A_prompt", "A_know", "A_retry", "B_generic", "C_domain", "C_know"]
    core, f21 = exp["core"], exp["finswe21"]
    p = core["contrasts"]["C_know vs A_know"]
    want = {"Resolved": [core["rate"][a] for a in arms],
            "Resolved within 40 calls": [core["rate_within_40"][a] for a in arms],
            "C_know vs A_know (primary)": [p["diff"], *p["ci"], p["prereg_p"], p["task_p"], p["tasks_plus"],
                                           -p["tasks_minus"]],
            **{k: [f21["resolved"][k][a] for a in arms] for k in ("v10", "v11", "v12", "v13")},
            "All four (of 12)": [sum(f21["resolved"][k][a] for k in f21["resolved"]) for a in arms],
            "… of which within 40 calls": [f21["within_40"][a] for a in arms]}
    v14 = exp.get("v14")
    if v14:  # Section 5.5 (exploratory offline-enforcement kernel)
        e_arms = ["A_know", "A_enforce", "C_know", "C_enforce"]
        want["Resolved (of 60)"] = [v14["core_resolved"][a] for a in e_arms]
        want["Resolved within 40 calls (of 60)"] = [v14["core_within_40"][a] for a in e_arms]
        for name, c in v14["contrasts"].items():
            want[name] = [c["diff"], *c["ci"], c["x_only"], c["y_only"], c["task_p_two_sided"]]
    bad = []
    for label, values in want.items():
        got = _row(text, label)
        if got is None:
            bad.append(f"C3 paper table row '{label}' not found")
        elif [round(v, 3) for v in got[:len(values)]] != [round(float(v), 3) for v in values]:
            bad.append(f"C3 paper row '{label}' says {got[:len(values)]}, expected.json says {values}")
    return bad


def c4(files):
    sums = ROOT / "results" / "SHA256SUMS"
    if not sums.exists():
        return ["C4 results/SHA256SUMS is missing"]
    listed, bad = set(), []
    for line in sums.read_text().splitlines():
        if line.strip():
            digest, rel = line.split(maxsplit=1)
            rel = rel.lstrip("*")
            listed.add(rel)
            p = ROOT / rel
            if not p.exists() or hashlib.sha256(p.read_bytes()).hexdigest() != digest:
                bad.append(f"C4 checksum mismatch or missing file: {rel}")
    bad += [f"C4 run record not in results/SHA256SUMS: {f}" for f in files
            if f.startswith("results/") and f.endswith("results.jsonl") and f not in listed]
    return bad


def c5():
    text = (ROOT / "paper" / "writeup.md").read_text(encoding="utf-8")
    bad = [f"C5 editorial marker in paper/writeup.md: {m.group(0)}" for m in MARKERS.finditer(text)]
    sub = next((ln.strip().strip("*") for ln in text.splitlines()[1:6] if ln.startswith("**")), "")
    if len(sub) > SUBTITLE_MAX:
        bad.append(f"C5 subtitle has {len(sub)} characters (limit {SUBTITLE_MAX})")
    return bad


def c7(body: str):
    bad = []
    sig = re.search(r"Contract:\s*AGENTS\.md@([0-9a-f]{8})", body)
    if not sig:
        bad.append("C7 PR body has no 'Contract: AGENTS.md@xxxxxxxx' signature")
    elif sig.group(1) != signature():
        bad.append(f"C7 PR is signed for AGENTS.md@{sig.group(1)}, but the contract is now @{signature()}: "
                   "read AGENTS.md again and re-sign")
    unticked = re.findall(r"^\s*[-*] \[ \]\s*(.*)$", body, flags=re.M)
    bad += [f"C7 unticked checklist item: {u[:80]}" for u in unticked]
    ticked = re.findall(r"^\s*[-*] \[[xX]\]\s*(.*)$", body, flags=re.M)
    missing = [c for c in CLAUSES if not any(re.match(rf"\**{c}\b", t) for t in ticked)]
    bad += [f"C7 no ticked checklist item for {c}" for c in missing]
    return bad


def c9(title: str | None, commit_range: str | None):
    bad = []
    if title is not None and not TITLE_RE.match(title):
        bad.append(f"C9 PR title does not match '[<AREA>] <summary>': {title[:80]!r}")
    if commit_range:
        out = subprocess.run(["git", "-C", str(ROOT), "log", "--no-merges", "--format=%h %s", commit_range],
                             capture_output=True, text=True)
        if out.returncode != 0:
            bad.append(f"C9 cannot read commits {commit_range}: {out.stderr.strip()[:120]}")
        for line in out.stdout.splitlines():
            sha, subject = line.split(" ", 1)
            if not COMMIT_RE.match(subject):
                bad.append(f"C9 commit {sha} subject does not match '<type>: <AREA> <summary>': {subject[:70]!r}")
    return bad


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--version", action="store_true", help="print the signature line and exit")
    ap.add_argument("--pr-body-env", help="name of the environment variable holding the PR body (checks C7)")
    ap.add_argument("--pr-title-env", help="name of the environment variable holding the PR title (checks C9)")
    ap.add_argument("--commit-range", help="git range whose commit subjects must follow the naming standard (C9)")
    ap.add_argument("--skip-reproduce", action="store_true", help="skip C3 (only for a quick local look)")
    a = ap.parse_args()
    if a.version:
        print(f"Contract: AGENTS.md@{signature()}")
        return 0
    files = tracked()
    problems = c1(files) + c2(files) + c4(files) + c5()
    problems += c3_paper()
    if not a.skip_reproduce:
        problems += c3()
    if a.pr_body_env is not None:
        problems += c7(os.environ.get(a.pr_body_env, ""))
    problems += c9(os.environ.get(a.pr_title_env, "") if a.pr_title_env else None, a.commit_range)
    for p in problems:
        print(f"✗ {p}")
    print(f"{'✓ contract holds' if not problems else f'✗ {len(problems)} contract violation(s)'} "
          f"(AGENTS.md@{signature()})")
    return 0 if not problems else 1


if __name__ == "__main__":
    sys.exit(main())
