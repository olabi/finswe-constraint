"""Claude Code PreToolUse hook for Bash: enforces AGENTS.md before a command runs.

- C6 (outward actions): a Kaggle submission or upload, a push or PR to another repository,
  and a repository visibility change always become an approval prompt for the user
  ("ask"), whatever the permission mode.
- C1–C5: `git commit` and `git push` are refused ("deny") while tools/contract_check.py
  fails, and the violations are given back as the reason.
Anything else passes through untouched.
"""

import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUTWARD = [
    (r"\bkaggle\s+competitions\s+submit\b", "a Kaggle competition submission"),
    (r"\bkaggle\s+kernels\s+push\b", "a Kaggle kernel push (uses GPU quota)"),
    (r"\bkaggle\s+datasets\s+(create|version)\b", "a Kaggle dataset upload"),
    (r"\bgh\s+repo\s+edit\b.*--visibility", "a repository visibility change"),
    # pushes and PRs anywhere but this repository's origin (ModulabsRAPIDSLAB/GUAM included)
    (r"\bgit\b[^|;&]*\bpush\b(?![^|;&]*\borigin\b)[^|;&]*\s(?!-)\S", "a push to a remote other than origin"),
    (r"\bgit\b[^|;&]*\bpush\b[^|;&]*github\.com[/:](?!olabi/finswe-constraint\b)", "a push to another repository"),
    (r"\bgh\s+pr\s+create\b[^|;&]*(-R|--repo)\s+(?!olabi/finswe-constraint\b)", "a PR to another repository"),
    (r"(?i)\b(git\s+push|gh\s+pr)\b[^|;&]*modulabsrapidslab", "a push or PR to ModulabsRAPIDSLAB"),
]


def decide(decision: str, reason: str) -> None:
    print(json.dumps({"hookSpecificOutput": {"hookEventName": "PreToolUse",
                                             "permissionDecision": decision,
                                             "permissionDecisionReason": reason}}, ensure_ascii=False))
    sys.exit(0)


def main() -> None:
    try:
        cmd = json.load(sys.stdin).get("tool_input", {}).get("command", "")
    except (ValueError, AttributeError):
        sys.exit(0)
    for pattern, what in OUTWARD:
        if re.search(pattern, cmd):
            decide("ask", f"AGENTS.md C6: this is {what}. It needs the user's explicit go-ahead in this conversation.")
    if re.search(r"\bgit\b[^|;&]*\b(commit|push)\b", cmd):
        r = subprocess.run([sys.executable, str(ROOT / "tools" / "contract_check.py")], cwd=ROOT,
                           capture_output=True, text=True)
        if r.returncode != 0:
            decide("deny", "AGENTS.md violated; fix these before committing or pushing:\n" + r.stdout.strip())
    sys.exit(0)


if __name__ == "__main__":
    main()
