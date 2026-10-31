"""FinSWE-Constraint pilot runner — one agent loop, three feedback conditions.

Mirrors the competition harness (swegemma, HARNESS_README §5–§7): the same six
workspace tools and JSON response shapes, 5,000-char command output, 150-line /
10,000-char read_file cap, three continuation nudges, and a 32k context served by
vLLM with the gemma4 tool/reasoning parsers. One thing differs on purpose:
`submit_patch` passes through an **enforced verification gate** chosen by the
condition:

  A_prompt   no gate. The system prompt already tells the agent to compile and test.
  B_generic  gate = generic executable checks (syntax, hygiene, visible tests)
  C_domain   gate = generic + domain invariant checks (harness/verifiers/domain)

If the gate fails and correction rounds remain, `submit_patch` returns
`VerificationFailed` with structured feedback and the session continues.
Otherwise the patch is accepted. The system prompt is identical across conditions,
so the gate is the only manipulated variable.

Scoring uses the hidden tests (tasks/<id>/tests.patch) in a fresh copy of the
snapshot, which the gate never sees.
"""

from __future__ import annotations

import collections
import json
import os
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
import time
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Callable

CONDITIONS = {"A_prompt": None, "A_know": None, "A_retry": "placebo", "B_generic": "generic",
              "C_domain": "all", "C_know": "all"}
# *_know conditions get the domain invariants the C gate checks (id / title / scenario /
# expected, generated from the verifier itself) in the user prompt up front. A_know vs
# C_know isolates enforcement: same knowledge, gate on/off ("knowing is not enforcing").
KNOW = {"A_know", "C_know"}
# A_retry is the placebo control: the first submit_patch is bounced with a content-free
# "re-check your patch" message and the same extra tool calls a failed gate grants,
# so B/C gains can be separated from "one more chance + more budget".
PLACEBO_MSG = ("Patch NOT submitted yet: final review step. Re-check your change against the "
               "issue and the existing code, verify it, then call submit_patch again.")

# Commands that reach outside the workspace toward answers/verifiers invalidate the run.
CONTAMINATION = re.compile(r"/kaggle/input|/kaggle/working|finswe|hidden\.b64|tests\.patch|"
                           r"gold\.patch|verifiers/domain|eval\.json", re.I)

# Harness limits (HARNESS_README §5.2 / §6)
MAX_STDOUT = 5000
READ_MAX_LINES = 150
READ_MAX_CHARS = 10000
MAX_NUDGES = 3
MIN_OUTPUT_TOKENS = 1024  # context-overflow retry: below this, report the error instead
NUDGE_NORMAL = ("Please continue your work using the available tools, or call submit_patch "
                "when you have completed and verified your changes.")
NUDGE_LENGTH = ("Your previous response reached the token limit while thinking before a tool call "
                "was completed. Do NOT repeat your analysis in thought—keep reasoning under a few "
                "sentences and emit your next tool call immediately, or call submit_patch when you "
                "have completed and verified your changes.")


@dataclass
class Budget:
    max_tool_calls: int = 40
    max_minutes: float = 12.0
    max_turns: int = 80
    command_timeout_s: int = 300
    correction_rounds: int = 2  # gate failures returned to the agent before forced acceptance
    correction_calls: int = 10  # extra tool calls granted per bounced submission (B/C/placebo)
    placebo_rounds: int = 1     # A_retry: unconditional bounces
    context_limit: int = 32768
    max_output_tokens: int = 8192
    compact_at: int = 24000  # prompt tokens: elide oldest tool outputs beyond this


# ── data ──────────────────────────────────────────────────────────────────
@dataclass
class Task:
    id: str
    dir: Path
    snapshot: Path
    issue: str
    eval: dict
    spec: dict


def load_tasks(data_dir: Path, only: list[str] | None = None) -> list[Task]:
    out = []
    for d in sorted((data_dir / "tasks").iterdir()):
        if not (d / "task.json").exists():
            continue
        spec = json.loads((d / "task.json").read_text())
        if only and spec["id"] not in only:
            continue
        out.append(Task(spec["id"], d, data_dir / "snapshots" / f"{spec['id']}.tgz",
                        (d / "issue.md").read_text(), json.loads((d / "eval.json").read_text()), spec))
    return out


def hidden_tests(task: Task) -> str:
    """Hidden tests ship zlib+base64-encoded (hidden.b64) so a stray grep cannot read them."""
    blob = task.dir / "hidden.b64"
    if blob.exists():
        import base64, zlib  # noqa: E401,PLC0415
        return zlib.decompress(base64.b64decode(blob.read_bytes())).decode()
    return (task.dir / "tests.patch").read_text()


def sh(cmd, cwd=None, timeout=None, env=None) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=timeout, env=env)


def materialize(task: Task, dest: Path) -> Path:
    """Fresh workspace from the snapshot + a 'baseline' commit (harness §4.2 step 7)."""
    if dest.exists():
        shutil.rmtree(dest)
    dest.mkdir(parents=True)
    snap = task.snapshot
    if snap.is_file():
        with tarfile.open(snap) as tf:
            tf.extractall(dest, filter="data") if sys.version_info >= (3, 12) else tf.extractall(dest)
    else:  # Kaggle may auto-extract uploaded archives into a directory
        cands = [snap, snap.with_suffix(""), snap.parent / task.id]
        src = next((c for c in cands if c.is_dir()), None)
        if src is None:
            raise FileNotFoundError(f"snapshot for {task.id} not found near {snap}")
        inner = [p for p in src.iterdir()]
        if len(inner) == 1 and inner[0].is_dir() and not (src / task.spec.get("pkg", "ai_trader")).exists():
            src = inner[0]  # archive extracted into a single wrapper folder
        shutil.rmtree(dest)
        shutil.copytree(src, dest)
    sh(["git", "init", "-q"], cwd=dest)
    (dest / ".git" / "info").mkdir(parents=True, exist_ok=True)
    (dest / ".git" / "info" / "exclude").write_text(
        "__pycache__/\n*.pyc\n.pytest_cache/\n*.egg-info/\nbuild/\ndist/\n.coverage\n")
    sh(["git", "add", "-A"], cwd=dest)
    sh(["git", "-c", "user.name=finswe", "-c", "user.email=finswe@local",
        "commit", "-qm", "baseline", "--allow-empty"], cwd=dest)
    return dest


def py_env(work: Path, python: str | None = None) -> dict:
    """Environment for agent commands and tests. A task with its own interpreter (a public
    task's venv) puts that venv first on PATH, so `python` / `pytest` resolve to it."""
    env = {**os.environ, "PYTHONPATH": str(work), "PYTHONDONTWRITEBYTECODE": "1"}
    if python and Path(python).parent != Path(sys.executable).parent:
        env["PATH"] = f"{Path(python).parent}{os.pathsep}{env.get('PATH', '')}"
        env["VIRTUAL_ENV"] = str(Path(python).parents[1])
    return env


# ── tools (harness semantics) ─────────────────────────────────────────────
def _ok(**kw) -> str:
    return json.dumps({"status": "ok", **kw}, ensure_ascii=False)


def _err(kind: str, msg: str, **details) -> str:
    return json.dumps({"status": "error", "error_type": kind, "error_message": msg,
                       "details": details}, ensure_ascii=False)


TOOL_SPECS = [
    {"type": "function", "function": {
        "name": "run_command", "description": "Executes a shell command in /bin/bash -c inside /workspace.",
        "parameters": {"type": "object", "properties": {"command": {"type": "string"}},
                       "required": ["command"]}}},
    {"type": "function", "function": {
        "name": "read_file",
        "description": "Reads a file from /workspace with 1-indexed inclusive line slicing "
                       "(max 150 lines / 10000 chars per call).",
        "parameters": {"type": "object", "properties": {
            "filepath": {"type": "string"}, "start_line": {"type": "integer"},
            "end_line": {"type": "integer"}}, "required": ["filepath"]}}},
    {"type": "function", "function": {
        "name": "edit_file",
        "description": "Replaces old_string with new_string in an existing non-empty file in /workspace.",
        "parameters": {"type": "object", "properties": {
            "filepath": {"type": "string"}, "old_string": {"type": "string"},
            "new_string": {"type": "string"}, "allow_multiple": {"type": "boolean"}},
            "required": ["filepath", "old_string", "new_string"]}}},
    {"type": "function", "function": {
        "name": "write_file",
        "description": "Creates or overwrites a file at /workspace/<filepath>, creating parent dirs.",
        "parameters": {"type": "object", "properties": {
            "filepath": {"type": "string"}, "content": {"type": "string"}},
            "required": ["filepath", "content"]}}},
    {"type": "function", "function": {
        "name": "get_status", "description": "Returns live budget consumption and patch status.",
        "parameters": {"type": "object", "properties": {}}}},
    {"type": "function", "function": {
        "name": "submit_patch",
        "description": "Stages untracked files (git add -N .) and captures git diff HEAD from /workspace.",
        "parameters": {"type": "object", "properties": {}}}},
]


def harness_apply_replacement():
    """The competition harness's own edit engine; local copy only when swegemma is absent."""
    try:
        from swegemma.edit import apply_replacement  # noqa: PLC0415
        return apply_replacement, "swegemma"
    except ImportError:
        sys.path.insert(0, str(Path(__file__).resolve().parent / "_vendor"))
        from swegemma_edit import apply_replacement  # noqa: PLC0415
        return apply_replacement, "vendored-copy"


class Session:
    """One agent attempt on one task under one condition."""

    def __init__(self, task: Task, condition: str, work: Path, budget: Budget,
                 verifier: Callable[[str, Path, str], dict] | None, python: str):
        self.task, self.condition, self.work, self.b = task, condition, work, budget
        self.verifier, self.python = verifier, python
        self.level = CONDITIONS[condition]
        self.t0 = time.time()
        self.tool_calls = 0
        self.turns = 0
        self.llm_calls = 0
        self.prompt_tokens = 0
        self.completion_tokens = 0
        self.gate_rounds: list[dict] = []
        self.submitted_patch: str | None = None
        self.patch_submitted = False
        self.end_reason = ""
        self.contaminated: list[str] = []
        self.max_calls = budget.max_tool_calls  # grows by correction_calls per bounce
        self.know_brief_chars = 0  # >0 iff the invariant brief actually reached the prompt
        self.edit_tiers: dict[str, int] = collections.Counter()  # which edit tier applied
        self.malformed_calls = 0  # tool calls whose arguments failed to bind (parser damage)
        self.repeated_malformed = 0  # identical malformed calls sent again (the hint below fired)
        self._last_malformed: tuple[str, str] | None = None
        self.edit_engine = ""
        self.first_patch: str | None = None

    # helpers
    def remaining_s(self) -> float:
        return self.b.max_minutes * 60 - (time.time() - self.t0)

    def _path(self, p: str) -> Path:
        p = p.strip()
        if p.startswith("/workspace"):
            p = p[len("/workspace"):].lstrip("/")
        q = (self.work / p).resolve()
        if not q.is_relative_to(self.work.resolve()):
            raise PermissionError("path outside /workspace")
        return q

    def _rewrite(self, cmd: str) -> str:  # subprocess backend: /workspace → sandbox dir
        return cmd.replace("/workspace", str(self.work))

    def _budget_note(self, payload: str) -> str:
        left = self.max_calls - self.tool_calls
        if self.max_calls >= 20 and left <= 10:
            d = json.loads(payload)
            d["budget_warning"] = (f"Only {left} tool call(s) remaining ({self.tool_calls}/"
                                   f"{self.max_calls} used). Finalize your edits and call "
                                   "submit_patch soon.")
            return json.dumps(d, ensure_ascii=False)
        return payload

    def _diff(self) -> str:
        sh(["git", "add", "-N", "."], cwd=self.work)
        return sh(["git", "diff", "HEAD"], cwd=self.work).stdout

    # tools
    def run_command(self, command: str) -> str:
        if CONTAMINATION.search(command):
            self.contaminated.append(command[:300])
        t = min(self.b.command_timeout_s, max(5, int(self.remaining_s())))
        try:
            r = sh(["/bin/bash", "-c", self._rewrite(command)], cwd=self.work, timeout=t,
                   env=py_env(self.work, self.python))
        except subprocess.TimeoutExpired:
            return _err("TimeoutExceeded", f"Command exceeded {t}s")
        out = r.stdout[:MAX_STDOUT].replace(str(self.work), "/workspace")
        err = r.stderr[:MAX_STDOUT].replace(str(self.work), "/workspace")
        if r.returncode == 0:
            return _ok(stdout=out, exit_code=0)
        return _err("CommandError", f"Command failed with exit code {r.returncode}",
                    stdout=out, stderr=err, exit_code=r.returncode)

    def read_file(self, filepath: str, start_line: int | None = None, end_line: int | None = None) -> str:
        try:
            p = self._path(filepath)
            lines = p.read_text(encoding="utf-8", errors="replace").splitlines()
        except Exception as e:
            return _err(type(e).__name__, str(e))
        s = max(1, start_line or 1)
        e = min(len(lines), end_line or len(lines), s + READ_MAX_LINES - 1)
        body = "\n".join(f"{i}: {lines[i - 1]}" for i in range(s, e + 1))[:READ_MAX_CHARS]
        return _ok(content=body, start_line=s, end_line=e, total_lines=len(lines))

    def edit_file(self, filepath: str, old_string: str, new_string: str,
                  allow_multiple: bool = False) -> str:
        """Harness-identical: swegemma.edit.apply_replacement (exact → flexible → regex → unescaped)."""
        try:
            apply_replacement, engine = harness_apply_replacement()
            p = self._path(filepath)
            if not p.exists():
                raise FileNotFoundError(f"File '{filepath}' not found in workspace.")
            with open(p, encoding="utf-8", errors="replace", newline="") as f:
                content = f.read()
            if len(content) == 0:
                raise ValueError(f"File '{filepath}' is empty. Use write_file to populate an empty or newly created file.")
            allow = (allow_multiple.strip().lower() in ("true", "1", "yes")
                     if isinstance(allow_multiple, str) else bool(allow_multiple))
            res = apply_replacement(content, old_string, new_string, filepath=filepath, allow_multiple=allow)
            with open(p, "w", encoding="utf-8", newline="") as f:
                f.write(res.new_content)
        except Exception as e:
            self.edit_tiers["fail"] += 1
            return _err("FileEditError", str(e))
        self.edit_tiers[res.strategy] += 1
        self.edit_engine = engine
        diff = res.diff[:MAX_STDOUT]
        return _ok(filepath=filepath, occurrences=res.occurrences, strategy=res.strategy,
                   diff=diff, is_truncated=len(res.diff) > MAX_STDOUT)

    def write_file(self, filepath: str, content: str) -> str:
        """Harness-identical: content is written as given (no unescaping)."""
        try:
            p = self._path(filepath)
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(content, encoding="utf-8")
            self.edit_tiers["write"] += 1
        except Exception as e:
            return _err("FileWriteError", str(e))
        return _ok(filepath=filepath, size=len(content))

    def get_status(self) -> str:
        return _ok(tool_calls_used=self.tool_calls, tool_calls_budget=self.max_calls,
                   time_remaining_s=int(self.remaining_s()), turns_used=self.turns,
                   patch_submitted=self.patch_submitted, gate_rounds_used=len(self.gate_rounds))

    def submit_patch(self) -> str:
        patch = self._diff()
        if self.first_patch is None:  # counterfactual: what the agent would have shipped ungated
            self.first_patch = patch
        files = len(re.findall(r"^diff --git ", patch, flags=re.M))
        if self.level is None or self.verifier is None:
            return self._accept(patch, files)
        if self.level == "placebo":
            if len(self.gate_rounds) >= self.b.placebo_rounds:
                return self._accept(patch, files)
            self.gate_rounds.append({"round": len(self.gate_rounds) + 1, "failed": ["PLACEBO"],
                                     "t": round(time.time() - self.t0, 1), "tool_calls": self.tool_calls})
            self.max_calls = max(self.max_calls, self.tool_calls) + self.b.correction_calls
            return _err("ReviewRequested", PLACEBO_MSG, extra_tool_calls=self.b.correction_calls)
        rep = self.verifier(self.task.id, self.work, self.level)
        failed = [r["id"] for r in rep["results"] if r["status"] != "pass"]
        errored = [r["id"] for r in rep["results"] if r["status"] == "error"]
        self.gate_rounds.append({"round": len(self.gate_rounds) + 1, "failed": failed,
                                 "errored": errored, "checks": len(rep["results"]),
                                 "t": round(time.time() - self.t0, 1), "tool_calls": self.tool_calls})
        if not failed:
            return self._accept(patch, files, verified=True)
        if len(self.gate_rounds) > self.b.correction_rounds:
            return self._accept(patch, files, verified=False)
        from feedback import render  # noqa: PLC0415 (on sys.path via the data dir)
        self.max_calls = max(self.max_calls, self.tool_calls) + self.b.correction_calls
        return _err("VerificationFailed",
                    "Patch NOT submitted: verification gate failed. Fix the issues below and call "
                    "submit_patch again.", feedback=render(rep),
                    rounds_left=self.b.correction_rounds - len(self.gate_rounds) + 1,
                    extra_tool_calls=self.b.correction_calls)

    def _accept(self, patch: str, files: int, verified: bool | None = None) -> str:
        self.submitted_patch, self.patch_submitted = patch, True
        extra = {} if verified is None else {"verified": verified}
        return _ok(patch_size=len(patch), files_changed=files, **extra)

    def dispatch(self, name: str, args: dict) -> str:
        if name not in {t["function"]["name"] for t in TOOL_SPECS}:
            return _err("UnknownTool", f"no tool named {name}")
        counted = name != "submit_patch"
        if counted and self.tool_calls >= self.max_calls:
            return _err("BudgetExhausted", "tool call budget exhausted; call submit_patch")
        if counted:
            self.tool_calls += 1
        try:
            res = getattr(self, name)(**args)
        except TypeError as e:
            self.malformed_calls += 1
            msg = str(e)
            # v12: seed-2 runs re-sent one parser-damaged edit_file 30-50 times verbatim
            sig = (name, json.dumps(args, sort_keys=True))
            if sig == self._last_malformed:
                self.repeated_malformed += 1
                msg += (f". This exact call already failed. The tool received only {sorted(args)}: "
                        "re-send it with every required argument as a separate field, "
                        "or make the change with run_command")
            self._last_malformed = sig
            res = _err("InvalidArguments", msg)
        else:
            self._last_malformed = None
        return self._budget_note(res) if counted else res


# ── prompts ───────────────────────────────────────────────────────────────
def user_prompt(task: Task, s: Session, repo: str = "ai-trader") -> str:
    """Mirrors build_agent_prompt (HARNESS_README §5.2)."""
    layout = sh(["bash", "-c", "find . -maxdepth 3 -not -path './.git*' -not -name '*.pyc' "
                 "-not -path '*/__pycache__*' | sort | head -150"], cwd=s.work).stdout
    return (f"You are evaluating a software engineering task for repository {repo}.\n\n"
            f"Problem Statement:\n{task.issue}\n\n"
            "## Task Budget (Session terminates when any budget is exhausted)\n"
            f"- Time allowance: {s.b.max_minutes:.1f} minutes\n"
            f"- Tool calls allowance: {s.b.max_tool_calls} calls\n"
            f"- Max loop iterations: {s.b.max_turns} turns\n\n"
            "## Execution Environment Rules\n"
            f"- Single command timeout: {s.b.command_timeout_s} seconds (commands exceeding this fail "
            "without ending the session)\n"
            f"- Command output limit: {MAX_STDOUT} characters\n"
            f"- File view limit: {READ_MAX_LINES} lines per read_file call\n"
            f"- File character limit: {READ_MAX_CHARS} characters per read_file call\n"
            "- Environment is offline (no network/PyPI access). All repository and test "
            "dependencies are ALREADY pre-installed. Do NOT attempt to run pip install or "
            "download packages.\n\n"
            "## Instructions\n"
            "0. Work strictly under /workspace.\n"
            "1. Inspect existing code conventions before editing.\n"
            "2. Make the smallest correct source change that resolves the issue.\n"
            "3. Verify with targeted checks (python3 -c, py_compile, focused pytest).\n"
            "4. Call submit_patch once complete.\n"
            "5. Then reply with one short final message.\n\n"
            f"## Workspace Layout\n{layout}")


def invariant_brief(task: Task, work: Path, python: str) -> str:
    """Natural-language statement of the task's domain invariants (no gate, no observed)."""
    from feedback import describe  # noqa: PLC0415 (on sys.path via the data dir)

    checks = describe(task.id, work, Path(python))
    if not checks:
        return ""
    lines = ["## Domain invariants",
             "The change must preserve these properties of the trading system (they are what "
             "domain experts check; their test code is not provided):"]
    for c in checks:
        lines += [f"- {c['title']}", f"  scenario: {c['scenario']}", f"  expected: {c['expected']}"]
    return "\n".join(lines) + "\n"


SYSTEM_PROMPT_FILE = "system.md"  # credited adaptation of the public 0.12/0.15 bundle prompt


# ── LLM client (OpenAI-compatible vLLM endpoint) ──────────────────────────
@dataclass
class LLMConfig:
    base_url: str = "http://127.0.0.1:8000/v1"
    model: str = "gemma"
    temperature: float = 0.2
    top_p: float = 0.95
    top_k: int = 40
    max_tokens: int = 8192
    enable_thinking: bool = False
    timeout_s: int = 600
    seed: int | None = None


def vllm_policy(cfg: LLMConfig) -> Callable[[list, list], dict]:
    def call(messages: list, tools: list) -> dict:
        body = {"model": cfg.model, "messages": messages, "tools": tools, "tool_choice": "auto",
                "temperature": cfg.temperature, "top_p": cfg.top_p, "max_tokens": cfg.max_tokens,
                "top_k": cfg.top_k,
                "chat_template_kwargs": {"enable_thinking": cfg.enable_thinking}}
        if cfg.seed is not None:
            body["seed"] = cfg.seed
        req = urllib.request.Request(f"{cfg.base_url}/chat/completions",
                                     data=json.dumps(body).encode(),
                                     headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=cfg.timeout_s) as r:
                return json.loads(r.read())
        except urllib.error.HTTPError as e:
            msg = e.read().decode(errors="replace")[:2000]
            # prompt + max_tokens over the context: retry once with the output room that is left
            m = re.search(r"maximum context length is (\d+) tokens.*?(\d+) input tokens", msg, re.S)
            room = int(m.group(1)) - int(m.group(2)) - 64 if m else 0
            if room >= MIN_OUTPUT_TOKENS and body["max_tokens"] > room:
                body["max_tokens"] = room
                req = urllib.request.Request(req.full_url, data=json.dumps(body).encode(),
                                             headers={"Content-Type": "application/json"})
                try:
                    with urllib.request.urlopen(req, timeout=cfg.timeout_s) as r:
                        return json.loads(r.read())
                except urllib.error.HTTPError as e2:
                    msg = e2.read().decode(errors="replace")[:2000]
            return {"error": {"code": e.code, "message": msg}}
    return call


# ── the loop ──────────────────────────────────────────────────────────────
def _compact(messages: list, keep_last: int = 6) -> int:
    """Elide the oldest tool outputs; returns how many were elided."""
    tool_idx = [i for i, m in enumerate(messages) if m["role"] == "tool"
                and not m["content"].startswith("[elided")]
    n = 0
    for i in tool_idx[:-keep_last]:
        messages[i]["content"] = "[elided to save context — re-run the tool if you need it]"
        n += 1
    return n


def run_session(task: Task, condition: str, policy: Callable[[list, list], dict], *,
                workroot: Path, system_prompt: str, budget: Budget,
                verifier: Callable[[str, Path, str], dict] | None, python: str,
                trace_path: Path | None = None) -> Session:
    work = materialize(task, workroot / f"{task.id}__{condition}" / "workspace")
    s = Session(task, condition, work, budget, verifier, python)
    prompt = user_prompt(task, s, task.spec.get("repo_name", "ai-trader"))
    brief = invariant_brief(task, work, python) if condition in KNOW else ""
    if brief:  # inserted before the workspace layout, after the instructions
        prompt = prompt.replace("## Workspace Layout", brief + "\n## Workspace Layout", 1)
    s.know_brief_chars = len(brief) if "## Domain invariants" in prompt else 0
    messages = [{"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt}]
    trace = open(trace_path, "w") if trace_path else None
    nudges = 0

    def log(kind, **kw):
        if trace:
            trace.write(json.dumps({"t": round(time.time() - s.t0, 2), "kind": kind, **kw},
                                   ensure_ascii=False) + "\n")
            trace.flush()

    s.t0 = time.time()  # budget clock starts after prompt construction (equal for all conditions)
    log("prompt", chars=len(prompt), know_brief_chars=s.know_brief_chars)
    try:
        while True:
            if s.remaining_s() <= 0:
                s.end_reason = "time"; break
            if s.turns >= budget.max_turns:
                s.end_reason = "turns"; break
            s.turns += 1
            resp = policy(messages, TOOL_SPECS)
            s.llm_calls += 1
            if "error" in resp:
                msg = str(resp["error"].get("message", ""))
                log("llm_error", error=msg[:500])
                if re.search(r"maximum context|context length|max_model_len|too long", msg, re.I) \
                        and _compact(messages, keep_last=2):
                    continue
                s.end_reason = "llm_error"; break
            usage = resp.get("usage") or {}
            s.prompt_tokens += usage.get("prompt_tokens", 0)
            s.completion_tokens += usage.get("completion_tokens", 0)
            choice = resp["choices"][0]
            msg = choice["message"]
            calls = msg.get("tool_calls") or []
            log("assistant", content=(msg.get("content") or "")[:4000],
                tool_calls=[{"name": c["function"]["name"], "args": c["function"]["arguments"][:4000]}
                            for c in calls], finish=choice.get("finish_reason"),
                prompt_tokens=usage.get("prompt_tokens"))
            messages.append({"role": "assistant", "content": msg.get("content") or "",
                             **({"tool_calls": calls} if calls else {})})
            for c in calls:
                name = c["function"]["name"]
                try:
                    args = json.loads(c["function"]["arguments"] or "{}")
                except json.JSONDecodeError as e:
                    out = _err("InvalidArguments", f"arguments are not valid JSON: {e}")
                else:
                    out = s.dispatch(name, args if isinstance(args, dict) else {})
                log("tool", name=name, result=out[:4000])
                messages.append({"role": "tool", "tool_call_id": c.get("id", name), "content": out})
            if s.patch_submitted:
                s.end_reason = "submitted"; break
            if usage.get("prompt_tokens", 0) > budget.compact_at:
                log("compact", elided=_compact(messages))
            if calls:
                nudges = 0
                continue
            nudges += 1
            if nudges > MAX_NUDGES:
                s.end_reason = "nudges"; break
            length = str(choice.get("finish_reason", "")).lower() in ("length", "max_tokens")
            messages.append({"role": "user", "content": NUDGE_LENGTH if length else NUDGE_NORMAL})
    finally:
        if s.submitted_patch is None:  # harness fallback: git add -N . && git diff HEAD
            s.submitted_patch = s._diff()
            s.end_reason = s.end_reason or "no_submit"
        log("end", reason=s.end_reason, patch_size=len(s.submitted_patch or ""))
        if trace:
            trace.close()
    return s


# ── scoring with hidden tests (never shown to the agent) ──────────────────
def run_tests(work: Path, python: str) -> dict[str, str]:
    xml = work / ".finswe-junit.xml"
    sh([python, "-m", "pytest", "-q", "-p", "no:cacheprovider", f"--junitxml={xml}", "tests"],
       cwd=work, env=py_env(work, python), timeout=900)
    out: dict[str, str] = {}
    if xml.exists():
        for tc in ET.parse(xml).getroot().iter("testcase"):
            nodeid = f"{tc.get('classname', '').replace('.', '/')}.py::{tc.get('name')}"
            status = "passed"
            for ch in tc:
                status = "failed" if ch.tag in ("failure", "error") else ("skipped" if ch.tag == "skipped" else status)
            out[nodeid] = status
    return out


def _apply(patch: str, work: Path) -> bool:
    if not patch.strip():
        return True
    pf = work.parent / f"cand-{os.getpid()}.patch"
    pf.write_text(patch)
    for cmd in (["git", "apply", "--whitespace=nowarn", str(pf)],
                ["git", "apply", "--whitespace=nowarn", "--3way", str(pf)],
                ["patch", "-p1", "--batch", "-i", str(pf)]):
        if sh(cmd, cwd=work).returncode == 0:
            return True
    return False


_ENV_EXCLUDED: dict[tuple[str, str], list[str]] = {}


def env_excluded(task: Task, python: str, root: Path) -> list[str]:
    """PASS_TO_PASS tests that fail at base *in this environment* (cached per task).

    They cannot discriminate patches here (e.g. a test needing an optional package that
    the offline image lacks), so scoring drops them and records which ones.
    """
    key = (task.id, python)
    if key not in _ENV_EXCLUDED:
        res = _score_raw(task, "", python, root / "env-baseline")
        _ENV_EXCLUDED[key] = sorted(t for t in task.eval["PASS_TO_PASS"] if res.get(t) != "passed")
    return _ENV_EXCLUDED[key]


def _score_raw(task: Task, patch: str, python: str, root: Path) -> dict | None:
    work = materialize(task, root / "workspace")
    if not _apply(patch, work):
        return None
    tests = hidden_tests(task)
    for f in re.findall(r"^\+\+\+ b/(\S+)", tests, flags=re.M):
        if (work / f).exists():
            sh(["git", "checkout", "HEAD", "--", f], cwd=work)
    sh(["git", "clean", "-fdq", "tests"], cwd=work)
    if not _apply(tests, work):
        raise RuntimeError(f"{task.id}: hidden tests did not apply")
    return run_tests(work, python)


def score(task: Task, patch: str, python: str, root: Path) -> dict:
    excluded = env_excluded(task, python, root)
    work = materialize(task, root / "score" / "workspace")
    applied = _apply(patch, work)
    tests = hidden_tests(task)
    for f in re.findall(r"^\+\+\+ b/(\S+)", tests, flags=re.M):
        if (work / f).exists():
            sh(["git", "checkout", "HEAD", "--", f], cwd=work)
    sh(["git", "clean", "-fdq", "tests"], cwd=work)
    if not _apply(tests, work):
        return {"applied": applied, "resolved": False, "error": "hidden tests did not apply"}
    res = run_tests(work, python) if applied else {}
    p2p_all = [t for t in task.eval["PASS_TO_PASS"] if t not in excluded]
    f2p = [t for t in task.eval["FAIL_TO_PASS"] if res.get(t) == "passed"]
    p2p = [t for t in p2p_all if res.get(t) == "passed"]
    return {"applied": applied,
            "resolved": applied and len(f2p) == len(task.eval["FAIL_TO_PASS"])
            and len(p2p) == len(p2p_all),
            "f2p": f"{len(f2p)}/{len(task.eval['FAIL_TO_PASS'])}",
            "p2p": f"{len(p2p)}/{len(p2p_all)}", "env_excluded": excluded}


@dataclass
class RunRecord:
    task: str
    condition: str
    seed: int
    resolved: bool
    applied: bool
    f2p: str
    p2p: str
    end_reason: str
    patch_size: int
    tool_calls: int
    llm_calls: int
    turns: int
    prompt_tokens: int
    completion_tokens: int
    wall_s: float
    gate_rounds: list = field(default_factory=list)
    first_gate_failed: list = field(default_factory=list)
    final_gate_passed: bool | None = None
    contaminated: list = field(default_factory=list)
    env_excluded: list = field(default_factory=list)
    know_brief_chars: int = 0
    edit_tiers: dict = field(default_factory=dict)
    malformed_calls: int = 0
    edit_engine: str = ""
    resolved_at_first_submit: bool | None = None  # hidden-test score of the first submitted patch
    repeated_malformed: int = 0


def run_one(task: Task, condition: str, seed: int, policy, *, root: Path, system_prompt: str,
            budget: Budget, verifier, python: str) -> RunRecord:
    run_root = Path(tempfile.mkdtemp(prefix=f"fsc-{task.id}-{condition}-", dir=root))
    traces = root / "traces"
    traces.mkdir(parents=True, exist_ok=True)
    s = run_session(task, condition, policy, workroot=run_root, system_prompt=system_prompt,
                    budget=budget, verifier=verifier, python=python,
                    trace_path=traces / f"{task.id}__{condition}__s{seed}.jsonl")
    sc = score(task, s.submitted_patch or "", python, run_root)
    (traces / f"{task.id}__{condition}__s{seed}.patch").write_text(s.submitted_patch or "")
    first = None
    if s.gate_rounds and s.first_patch is not None:  # gated runs only: within-run counterfactual
        first = (score(task, s.first_patch, python, run_root / "first")["resolved"]
                 if s.first_patch != s.submitted_patch else sc["resolved"])
        (traces / f"{task.id}__{condition}__s{seed}.first.patch").write_text(s.first_patch)
    shutil.rmtree(run_root, ignore_errors=True)
    g = s.gate_rounds
    return RunRecord(task.id, condition, seed, sc["resolved"], sc["applied"], sc.get("f2p", ""),
                     sc.get("p2p", ""), s.end_reason, len(s.submitted_patch or ""), s.tool_calls,
                     s.llm_calls, s.turns, s.prompt_tokens, s.completion_tokens,
                     round(time.time() - s.t0, 1), g, g[0]["failed"] if g else [],
                     (not g[-1]["failed"]) if g else None, s.contaminated, sc.get("env_excluded", []),
                     s.know_brief_chars, dict(s.edit_tiers), s.malformed_calls, s.edit_engine, first,
                     s.repeated_malformed)


def make_verifier(python: str):
    from feedback import check  # noqa: PLC0415

    def verify(task_id: str, work: Path, level: str) -> dict:
        return check(task_id, work, Path(python), level)
    return verify


def as_dict(r: RunRecord) -> dict:
    return asdict(r)
