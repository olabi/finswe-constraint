"""CPU unit test of the offline-enforcement switches (Budget.enforce_*), no LLM and no task data.

  python3 pilot/test_enforce.py

Builds a two-file git repo, drives Session tools directly and checks that:
- with the switches off, behaviour is unchanged (test edits, scratch files and pip go through);
- enforce_tools refuses test edits, new files outside code_dirs and network commands;
- enforce_verify refuses the first submit after an unverified edit, once per edit;
- enforce_cleanup drops stray files and restores edited tests before the diff.
"""
import json
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import finswe_pilot as fp  # noqa: E402


def _stub_engine():
    """The harness edit engine (swegemma) is not redistributed; a plain exact-match stand-in."""
    from types import SimpleNamespace

    def apply_replacement(content, old, new, filepath="", allow_multiple=False):
        n = content.count(old)
        if n != 1 and not (allow_multiple and n):
            raise ValueError(f"old_string found {n} times in {filepath}")
        return SimpleNamespace(new_content=content.replace(old, new), occurrences=n, strategy="exact", diff="")
    return apply_replacement, "test-stub"


try:
    fp.harness_apply_replacement()
except ImportError:
    fp.harness_apply_replacement = _stub_engine


def repo() -> Path:
    d = Path(tempfile.mkdtemp(prefix="enforce-"))
    (d / "pkg").mkdir()
    (d / "tests").mkdir()
    (d / "pkg" / "core.py").write_text("def f():\n    return 1\n")
    (d / "tests" / "test_core.py").write_text("def test_f():\n    assert True\n")
    for cmd in (["git", "init", "-q"], ["git", "add", "."],
                ["git", "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "base"]):
        subprocess.run(cmd, cwd=d, check=True)
    return d


def session(**flags) -> fp.Session:
    work = repo()
    task = fp.Task("T-1", work, work, "", {}, {"id": "T-1", "code_dirs": ["pkg/", "tests/"]})
    return fp.Session(task, "A_prompt", work, fp.Budget(**flags), verifier=None, python=sys.executable)


def status(res: str) -> str:
    d = json.loads(res)
    return d.get("details", {}).get("rule") or d["status"]


def main() -> int:
    # off (default): everything goes through, nothing is counted
    s = session()
    assert status(s.dispatch("write_file", {"filepath": "tests/test_core.py", "content": "x = 1\n"})) == "ok"
    assert status(s.dispatch("write_file", {"filepath": "repro.py", "content": "print(1)\n"})) == "ok"
    assert status(s.dispatch("submit_patch", {})) == "ok"
    assert "repro.py" in s.submitted_patch and "tests/test_core.py" in s.submitted_patch
    assert not s.enforced and not s.cleaned

    # enforce_tools
    s = session(enforce_tools=True)
    assert status(s.dispatch("write_file", {"filepath": "tests/test_core.py", "content": "x\n"})) == "tests"
    assert status(s.dispatch("write_file", {"filepath": "/workspace/conftest.py", "content": "x\n"})) == "tests"
    assert status(s.dispatch("edit_file", {"filepath": "tests/test_core.py", "old_string": "True",
                                           "new_string": "False"})) == "tests"
    assert status(s.dispatch("write_file", {"filepath": "repro.py", "content": "print(1)\n"})) == "scratch"
    assert status(s.dispatch("write_file", {"filepath": "pkg/new.py", "content": "y = 2\n"})) == "ok"
    assert status(s.dispatch("write_file", {"filepath": "pkg/core.py", "content": "def f():\n    return 2\n"})) == "ok"
    for cmd in ("pip install requests", "uv pip install x", "curl -s http://x", "git fetch origin"):
        assert status(s.dispatch("run_command", {"command": cmd})) == "network", cmd
    assert status(s.dispatch("run_command", {"command": "python -c 'print(1)' && git status --short"})) == "ok"
    assert dict(s.enforced) == {"tests": 3, "scratch": 1, "network": 4}, s.enforced
    assert not (s.work / "repro.py").exists() and "True" in (s.work / "tests" / "test_core.py").read_text()

    # enforce_verify: first submit after an edit is refused once; a command clears it
    s = session(enforce_verify=True)
    s.dispatch("edit_file", {"filepath": "pkg/core.py", "old_string": "return 1", "new_string": "return 2"})
    assert status(s.dispatch("submit_patch", {})) == "verify" and not s.patch_submitted
    assert status(s.dispatch("submit_patch", {})) == "ok"  # once per edit, never a dead end
    s = session(enforce_verify=True)
    s.dispatch("edit_file", {"filepath": "pkg/core.py", "old_string": "return 1", "new_string": "return 2"})
    s.dispatch("run_command", {"command": "python -m py_compile pkg/core.py"})
    assert status(s.dispatch("submit_patch", {})) == "ok" and s.enforced.get("verify", 0) == 0

    # enforce_cleanup: stray file and test edit never reach the patch, the fix does
    s = session(enforce_cleanup=True)
    s.dispatch("edit_file", {"filepath": "pkg/core.py", "old_string": "return 1", "new_string": "return 2"})
    s.dispatch("run_command", {"command": "echo junk > repro.py && echo 'x = 1' >> tests/test_core.py"})
    assert status(s.dispatch("submit_patch", {})) == "ok"
    assert "pkg/core.py" in s.submitted_patch
    assert "repro.py" not in s.submitted_patch and "tests/test_core.py" not in s.submitted_patch
    assert sorted(s.cleaned) == ["repro.py", "tests/test_core.py"], s.cleaned

    # *_enforce conditions switch all three on; *_know conditions keep them off
    for cond, on in (("A_enforce", True), ("C_enforce", True), ("A_know", False), ("C_know", False)):
        w = repo()
        ses = fp.Session(fp.Task("T", w, w, "", {}, {"id": "T"}), cond, w, fp.Budget(), None, sys.executable)
        assert (ses.b.enforce_tools, ses.b.enforce_verify, ses.b.enforce_cleanup) == (on,) * 3, cond
        assert (cond in fp.KNOW) and fp.CONDITIONS[cond] == fp.CONDITIONS[cond.replace("enforce", "know")]

    # guided tool calls: the request body asks vLLM for a required tool call
    assert fp.LLMConfig(base_url="http://x", model="m").guided_tools is False
    print("✓ offline enforcement: off by default; tools, verify and cleanup behave as specified")
    return 0


if __name__ == "__main__":
    sys.exit(main())
