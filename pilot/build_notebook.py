"""Generate finswe_pilot.ipynb (kept as code so the notebook is reviewable in diffs)."""

import json
from pathlib import Path

CELLS: list[tuple[str, str]] = []


def md(s):
    CELLS.append(("markdown", s.strip("\n")))


def code(s):
    CELLS.append(("code", s.strip("\n")))


md(r"""
# FinSWE-Constraint · pilot runner — *Knowing Is Not Enforcing*

Does an **enforced executable gate** make the competition model (`gemma-4-31b-it-qat-w4a16-ct`)
a more reliable developer agent than prompt-level best practices alone?

| Condition | What happens at `submit_patch` |
|---|---|
| **A_prompt** | accepted as is. The system prompt already says *compile, test, then submit* |
| **B_generic** | gate: syntax · patch hygiene · the repo's visible tests |
| **C_domain** | gate: B + per-task **domain invariant** checks |
| **A_retry** | placebo: first submit bounced with a content-free "re-check" message + the same extra calls |
| **A_know** | no gate, but the C gate's invariants (title / scenario / expected) are stated in the prompt |
| **C_know** | C_domain + the same invariant statement up front — **A_know vs C_know isolates enforcement** |

A failed gate returns `VerificationFailed` with structured feedback (scenario / expected /
observed), and the session continues for up to `correction_rounds`. Scoring always uses
**hidden tests the gate never sees**, applied in a fresh snapshot (two-phase, like the
harness).

The loop mirrors `swegemma` (HARNESS_README §5–§7): the same six workspace tools and JSON
shapes, the 5,000-char / 150-line limits, three nudges, a 32k context, and vLLM with the
`gemma4` tool and reasoning parsers. The system prompt is a credited adaptation of the public
0.12 / 0.15 bundle prompt (romanrozen), single-agent and identical across conditions.
Following Black Cat's noise finding, this is a **pilot**: 7 tasks are enough to debug the
pipeline and size effects, not to claim them.

**Inputs to attach:** the competition (`gemma-4-developer-agent`), the private dataset
`finswe-pilot-data`, and the Gemma 4 31B QAT W4A16 model. **Accelerator:** L4×4, internet off.
""")

code(r"""
CFG = {
    # 2x2 knowing × enforcing (A_know vs C_know is the PRIMARY contrast) + controls
    "conditions": ["A_prompt", "A_know", "A_retry", "B_generic", "C_domain", "C_know"],
    "tasks": ["PUB-21-ta-unpadded-date"],  # None = all; v9 runs only the public task FinSWE-21
    "seeds": [0, 1, 2],            # v5–v8: one seed per version (20 core tasks); v9: FinSWE-21 × 3 seeds
    "budget": dict(max_tool_calls=40, max_minutes=12.0, max_turns=80, command_timeout_s=300,
                   correction_rounds=2, correction_calls=10, placebo_rounds=1,
                   context_limit=32768, max_output_tokens=8192, compact_at=24000),
    "sampling": dict(temperature=0.2, top_p=0.95, top_k=40, max_tokens=8192, enable_thinking=False),
    "model_dir": None,             # None = auto-discover under /kaggle/input
    "vllm": dict(gpu_memory_utilization=0.90, max_model_len=32768, port=8000,
                 startup_timeout_s=2400),
    "max_runs": None,              # 20 tasks × 6 conditions = 120 runs per seed; v9: 1 × 6 × 3 = 18
    "public_env_wheels": {"tradingagents": "finswe-tradingagents-wheels"},  # env → wheel dataset
    "out_dir": "/kaggle/working/finswe-pilot",
}
""")

md("""
## 0 · Install the competition wheelhouse (vLLM, adk-submission, swegemma)
Same recipe as the host's *Getting Started* notebook: restore `+cu128` wheel names,
drop broken cutlass `.pth` hooks, and set offline vLLM env vars.
""")
code(r"""
import glob, importlib, os, subprocess, sys
from pathlib import Path

os.environ.update({
    "LITELLM_LOCAL_MODEL_COST_MAP": "True", "TRANSFORMERS_NO_TF": "1",
    "VLLM_WORKER_MULTIPROC_METHOD": "spawn", "VLLM_MEMORY_PROFILER_ESTIMATE_CUDAGRAPHS": "1",
    "VLLM_ENGINE_READY_TIMEOUT_S": "1200", "VLLM_NO_USAGE_STATS": "1", "OTEL_SDK_DISABLED": "true",
    "PYTORCH_CUDA_ALLOC_CONF": "expandable_segments:True",
})
WHEELHOUSE = next((p for p in [Path("/kaggle/input/datasets/metric/gemma-4-developer-agent-wheelhouse"),
                               Path("/kaggle/input/gemma-4-developer-agent-wheelhouse")] if p.exists()), None)
assert WHEELHOUSE, "attach dataset metric/gemma-4-developer-agent-wheelhouse"
for pat in ("/usr/local/lib/python*/dist-packages/*cutlass*.pth",
            "/usr/local/lib/python*/site-packages/*cutlass*.pth"):
    for pth in glob.glob(pat):
        try:
            os.unlink(pth)
        except OSError:
            pass
tmp_whl = Path("/tmp/wheelhouse"); tmp_whl.mkdir(parents=True, exist_ok=True)
for w in WHEELHOUSE.glob("*.whl"):
    if "cutlass" in w.name.lower():
        continue
    name = w.name.replace("cu128", "+cu128") if ("cu128" in w.name and "+" not in w.name) else w.name
    if not (tmp_whl / name).exists():
        os.symlink(w, tmp_whl / name)
wheels = sorted(str(w) for w in tmp_whl.glob("*.whl"))
print(f"installing {len(wheels)} wheels from {WHEELHOUSE} …")
subprocess.run([sys.executable, "-m", "pip", "install", "-q", "--no-deps", "--force-reinstall", *wheels],
               check=True)
importlib.invalidate_caches()
print("wheelhouse installed")
""")

md("""
### 0b · Capture the harness's own edit implementation (fidelity check)
Our runner approximates the harness's resilient `apply_replacement` (pilot/edit_tiers.py).
This copies the installed harness source files that define it (and the edit_file tool) into
the output, so the tiers can be compared line by line. Nothing is executed from them.
""")
code(r"""
import importlib.util, shutil as _sh
HSRC = Path(CFG["out_dir"]) / "harness_src"; HSRC.mkdir(parents=True, exist_ok=True)
hits = []
for pkg in ("adk_eval_core", "swegemma", "adk_submission"):
    spec = importlib.util.find_spec(pkg)
    if not spec or not spec.submodule_search_locations:
        print(f"{pkg}: not installed"); continue
    root = Path(list(spec.submodule_search_locations)[0])
    for f in root.rglob("*.py"):
        t = f.read_text(errors="ignore")
        if "def apply_replacement" in t or "def edit_file" in t or "def write_file" in t:
            dst = HSRC / f"{pkg}__{f.relative_to(root).as_posix().replace('/', '__')}"
            _sh.copy(f, dst); hits.append(dst.name)
print("captured:", hits or "none")
""")

md("## 1 · Locate data and environment")
code(r"""
import json, os, subprocess, sys, time, shutil, socket, urllib.request
from pathlib import Path

INPUT = Path("/kaggle/input")
def find_one(pattern, root=INPUT):
    hits = sorted(root.rglob(pattern)) if root.exists() else []
    return hits[0] if hits else None

runner = find_one("finswe_pilot.py")
assert runner, "attach the private dataset finswe-pilot-data (Add Input → Your Datasets)"
DATA = runner.parents[1]
sys.path[:0] = [str(DATA / "pilot"), str(DATA / "harness")]
import finswe_pilot as fp

OUT = Path(CFG["out_dir"]); OUT.mkdir(parents=True, exist_ok=True)
PY = sys.executable
COMP = (find_one("HARNESS_README.md") or Path("/nonexistent")).parent
print("data   :", DATA)
print("comp   :", COMP if COMP.exists() else "(competition not attached — fine for the pilot)")
print("python :", sys.version.split()[0], PY)
print("git    :", subprocess.run(["git", "--version"], capture_output=True, text=True).stdout.strip())
for mod in ("httpx", "pytest"):
    try:
        __import__(mod); print(f"{mod:<7}: ok")
    except ImportError:
        print(f"{mod:<7}: MISSING — ai-trader tests need it")
print(subprocess.run(["nvidia-smi", "--query-gpu=name,memory.total", "--format=csv,noheader"],
                     capture_output=True, text=True).stdout.strip() or "no GPU visible")
TASKS = fp.load_tasks(DATA, CFG["tasks"])
print(f"tasks  : {len(TASKS)} → {[t.id for t in TASKS]}")

# Public tasks (task.json "env") run on their own interpreter: a venv built offline from a
# wheel dataset (harness/public_task.py wheels). Agent commands, gates and scoring all use it.
PYS = {}
for env in sorted({t.spec["env"] for t in TASKS if t.spec.get("env")}):
    whl = find_one(f"*{CFG['public_env_wheels'][env]}*/requirements.txt") or find_one(
        "requirements.txt", INPUT / "datasets" / "kmmmvs" / CFG["public_env_wheels"][env])
    assert whl, f"attach the dataset {CFG['public_env_wheels'][env]} for env {env}"
    tags = {w.name.split("-")[-3] for w in whl.parent.glob("*.whl") if "-cp3" in w.name}
    here = f"cp{sys.version_info[0]}{sys.version_info[1]}"
    assert not tags or here in tags, f"wheels for {env} are built for {sorted(tags)}, this image is {here}"
    # outside /kaggle/working: thousands of venv files would otherwise become kernel output
    # and make `kaggle kernels output` crawl
    venv = Path(f"/tmp/venv-{env}")
    if not (venv / "bin" / "python").exists():
        # the image's Python has no ensurepip: make the venv bare and install with the image's pip
        subprocess.run([sys.executable, "-m", "venv", "--without-pip", str(venv)], check=True)
        subprocess.run([sys.executable, "-m", "pip", "--python", str(venv / "bin" / "python"),
                        "install", "-q", "--no-index", "--find-links", str(whl.parent), "-r", str(whl)],
                       check=True)
    PYS[env] = str(venv / "bin" / "python")
    print(f"venv   : {env} → {PYS[env]}")
def py_for(t):
    return PYS.get(t.spec.get("env"), PY)
""")

md("""
## 2 · CPU pre-flight (before spending GPU quota)
On every base snapshot, the domain gate must flag the bug and an empty patch must score
unresolved. Gold patches are not shipped; gold sanity was verified locally before export.
""")
code(r"""
pre = []
for t in TASKS:
    with __import__("tempfile").TemporaryDirectory() as tmp:
        w = fp.materialize(t, Path(tmp) / "w")
        rep = fp.make_verifier(py_for(t))(t.id, w, "domain")
        # fail, or error raised inside a check (e.g. FSC-006 base lacks the setting → TypeError),
        # counts as detection. D-IMPORT means the package itself would not load: broken env.
        flags = [r["id"] for r in rep["results"] if r["status"] != "pass" and r["id"] != "D-IMPORT"]
        errors = [f'{r["id"]}: {r["observed"][:120]}' for r in rep["results"] if r["status"] == "error"
                  and r["id"] in ("D-IMPORT",)]
        assert not errors, f"{t.id}: verifier could not load the package → {errors}"
        sc = fp.score(t, "", py_for(t), Path(tmp))
    pre.append((t.id, flags, sc["resolved"], sc["env_excluded"]))
    print(f"{t.id:<28} domain-flags={flags}  empty-patch-resolved={sc['resolved']}  "
          f"env-excluded P2P={sc['env_excluded']}")
controls = {t.id for t in TASKS if t.spec.get("family") == "control"}
assert all((f or tid in controls) and not r for tid, f, r, _ in pre), "pre-flight failed — do not start the GPU run"
# a few env-only failures (optional deps offline) are expected; many means a broken image
assert all(len(x) <= max(3, len(t.eval["PASS_TO_PASS"]) // 100) for t, (*_, x) in zip(TASKS, pre)), \
    "too many tests fail at base in this environment"
print("✅ pre-flight passed")
""")

md("## 3 · Model + vLLM server (same flags as the harness: TP=all GPUs, 32k, gemma4 parsers)")
code(r"""
HOST_MODEL_PATH = Path("/kaggle/input/models/google/gemma-4/other/gemma-4-31b-it-qat-w4a16-ct/2")

def discover_model():
    if CFG["model_dir"]:
        return Path(CFG["model_dir"])
    if (HOST_MODEL_PATH / "config.json").exists():
        return HOST_MODEL_PATH
    cands = []
    for cfgf in INPUT.rglob("config.json"):
        p = str(cfgf.parent).lower()
        if "31b" in p and ("qat" in p or "w4a16" in p) and any(cfgf.parent.glob("*.safetensors")):
            cands.append(cfgf.parent)
    for c in cands:
        print("candidate:", c)
    assert cands, ("Gemma 4 31B QAT W4A16 weights not found under /kaggle/input. "
                   "Attach the model (Add Input → Models) or set CFG['model_dir'].")
    return sorted(cands, key=lambda p: len(str(p)))[0]

MODEL_DIR = discover_model()
print("model:", MODEL_DIR)
try:
    import vllm; print("vllm", vllm.__version__)
except ImportError:
    raise SystemExit("vLLM is not importable in this image; the harness serves via vLLM — "
                     "check the competition's environment notes before continuing.")
""")

code(r"""
def gpu_count():
    out = subprocess.run(["nvidia-smi", "-L"], capture_output=True, text=True).stdout
    return max(1, len([l for l in out.splitlines() if l.startswith("GPU")]))

def port_open(port):
    with socket.socket() as s:
        return s.connect_ex(("127.0.0.1", port)) == 0

def start_vllm(extra):
    v = CFG["vllm"]
    cmd = [PY, "-m", "vllm.entrypoints.openai.api_server", "--model", str(MODEL_DIR),
           "--served-model-name", "gemma", "--tensor-parallel-size", str(gpu_count()),
           "--gpu-memory-utilization", str(v["gpu_memory_utilization"]),
           "--max-model-len", str(v["max_model_len"]), "--port", str(v["port"]),
           "--enable-auto-tool-choice", "--tool-call-parser", "gemma4", *extra]
    log = open(OUT / "vllm.log", "w")
    print(" ".join(cmd))
    return subprocess.Popen(cmd, stdout=log, stderr=subprocess.STDOUT), cmd

def wait_ready(proc):
    t0 = time.time()
    while time.time() - t0 < CFG["vllm"]["startup_timeout_s"]:
        if proc.poll() is not None:
            return False
        try:
            urllib.request.urlopen(f"http://127.0.0.1:{CFG['vllm']['port']}/v1/models", timeout=5)
            return True
        except Exception:
            time.sleep(10)
    return False

def start_harness_server():
    # exactly the harness/host configuration (adk_submission.VllmServer)
    import torch
    from adk_submission import VllmConfig, VllmServer
    n = torch.cuda.device_count()
    cfg = VllmConfig(
        model=str(MODEL_DIR), port=CFG["vllm"]["port"], host="127.0.0.1",
        tool_call_parser="gemma4", reasoning_parser="gemma4",
        max_model_len=CFG["vllm"]["max_model_len"],
        dtype="bfloat16" if (torch.cuda.is_available() and torch.cuda.is_bf16_supported()) else "auto",
        gpu_memory_utilization=CFG["vllm"]["gpu_memory_utilization"], enable_auto_tool_choice=True,
        enable_lora=True, max_loras=8, max_lora_rank=128,
        tensor_parallel_size=4 if n >= 4 else (2 if n >= 2 else 1),
        startup_timeout=CFG["vllm"]["startup_timeout_s"])
    srv = VllmServer(cfg, adapter_manifest=[])
    srv.start()
    return srv

SERVER = None
if not port_open(CFG["vllm"]["port"]):
    try:
        SERVER = start_harness_server()
        print("started via adk_submission.VllmServer")
    except Exception as e:
        print(f"adk_submission.VllmServer failed ({type(e).__name__}: {e}) — falling back to vLLM CLI")
        SERVER, cmd = start_vllm(["--reasoning-parser", "gemma4"])
        if not wait_ready(SERVER):
            print("".join(open(OUT / "vllm.log").readlines()[-25:]))
            SERVER.kill(); time.sleep(5)
            SERVER, cmd = start_vllm([])
            assert wait_ready(SERVER), "".join(open(OUT / "vllm.log").readlines()[-40:])
models = json.loads(urllib.request.urlopen(
    f"http://127.0.0.1:{CFG['vllm']['port']}/v1/models", timeout=30).read())
SERVED = models["data"][0]["id"]
print("✅ vLLM ready — served model id:", SERVED)
""")

md("## 4 · Tool-calling smoke test")
code(r"""
policy = fp.vllm_policy(fp.LLMConfig(**CFG["sampling"], model=SERVED,
                                     base_url=f"http://127.0.0.1:{CFG['vllm']['port']}/v1"))
resp = policy([{"role": "system", "content": "Use tools."},
               {"role": "user", "content": "Call get_status, nothing else."}], fp.TOOL_SPECS)
assert "error" not in resp, resp
m = resp["choices"][0]["message"]
print("tool_calls:", [c["function"]["name"] for c in (m.get("tool_calls") or [])])
print("usage     :", resp.get("usage"))
assert m.get("tool_calls"), "model did not emit a parsed tool call — check --tool-call-parser"
""")

md("## 5 · Pilot run (resumable: finished runs in results.jsonl are skipped)")
code(r"""
RESULTS = OUT / "results.jsonl"
done = set()
if RESULTS.exists():
    for line in RESULTS.read_text().splitlines():
        r = json.loads(line); done.add((r["task"], r["condition"], r["seed"]))
SYSTEM = (DATA / "pilot" / "system.md").read_text()
budget = fp.Budget(**CFG["budget"])
runs = 0
session_rows = []
for seed in CFG["seeds"]:
    llm = fp.LLMConfig(**CFG["sampling"], seed=seed, model=SERVED,
                       base_url=f"http://127.0.0.1:{CFG['vllm']['port']}/v1")
    pol = fp.vllm_policy(llm)
    for t in TASKS:
        for cond in CFG["conditions"]:          # conditions interleaved per task (drift-balanced)
            if (t.id, cond, seed) in done:
                continue
            if CFG["max_runs"] and runs >= CFG["max_runs"]:
                break
            rec = fp.run_one(t, cond, seed, pol, root=OUT, system_prompt=SYSTEM, budget=budget,
                             verifier=fp.make_verifier(py_for(t)), python=py_for(t))
            row = fp.as_dict(rec)
            with open(RESULTS, "a") as f:
                f.write(json.dumps(row, ensure_ascii=False) + "\n")
            runs += 1
            session_rows.append(rec)
            if len(session_rows) == 3 and all(r.end_reason == "llm_error" or r.tool_calls == 0
                                              for r in session_rows):
                raise SystemExit("first 3 runs all failed systemically (llm_error / no tool calls) — "
                                 "stopping to save GPU quota; inspect traces/ and vllm.log")
            print(f"{t.id:<28} {cond:<10} s{seed} resolved={str(rec.resolved):<5} "
                  f"end={rec.end_reason:<9} gates={[g['failed'] for g in rec.gate_rounds]} "
                  f"tools={rec.tool_calls} llm={rec.llm_calls} {rec.wall_s:.0f}s"
                  + (f"  ⚠ CONTAMINATED {rec.contaminated[:1]}" if rec.contaminated else ""))
print("runs this session:", runs)
""")

md("""
## 6 · Pre-registered analysis (paper/analysis-plan.md)
Primary contrast: **C_know vs A_know**. The verdict needs diff > min readable delta AND
placebo p ≤ 0.05. Seeds are run one per kernel version and merged locally with
`analyze.py`; a single version can only be descriptive.
""")
code(r"""
import collections
import analyze
rows_all = [json.loads(l) for l in RESULTS.read_text().splitlines() if l.strip()]
rows = [r for r in rows_all if not r.get("contaminated")]
# Step 1 — invariants: complete design, no duplicates, contamination reported
keys = [(r["task"], r["condition"], r["seed"]) for r in rows_all]
assert len(keys) == len(set(keys)), "duplicate runs"
expected = len(TASKS) * len(CFG["conditions"]) * len(CFG["seeds"])
print(f"runs {len(rows_all)}/{expected} | contaminated (dropped) {len(rows_all) - len(rows)}")
# Step 4 — the manipulated code paths actually ran
by = collections.defaultdict(list)
for r in rows:
    by[r["condition"]].append(r)
for c, rs in sorted(by.items()):
    gate = sum(1 for r in rs if r["gate_rounds"])
    errd = sum(1 for r in rs for g in r["gate_rounds"] for _ in g.get("errored", []))
    know = sum(1 for r in rs if r.get("know_brief_chars", 0) > 0)
    tiers = collections.Counter()
    for r in rs:
        tiers.update(r.get("edit_tiers", {}))
    bad = sum(r.get("malformed_calls", 0) for r in rs)
    print(f"{c:<10} runs {len(rs):>2} | gate fired {gate:>2} | errored checks {errd:>2} | invariant brief in prompt {know:>2}"
          f" | edit tiers {dict(tiers)} | malformed tool calls {bad}")
    if c in ("A_know", "C_know"):  # control tasks have no domain invariants → no brief by design
        need = sum(1 for r in rs if not r["task"].startswith("FSC-C"))
        assert know == need, f"{c}: invariant brief missing from some non-control prompts"
    if c in ("A_prompt", "A_know"):
        assert gate == 0, f"{c}: gate must never fire"
    engines = {r.get("edit_engine") for r in rs if r.get("edit_engine")}
    assert engines <= {"swegemma"}, f"{c}: edits must use the harness engine, got {engines}"
print()
print(analyze.report(rows))
""")

md("## 7 · Artifacts")
code(r"""
(OUT / "analysis.md").write_text(analyze.report(rows))
shutil.make_archive(str(OUT / "traces"), "zip", OUT / "traces")
print(sorted(p.name for p in OUT.iterdir()))
""")


def main():
    nb = {"nbformat": 4, "nbformat_minor": 5,
          "metadata": {"kernelspec": {"name": "python3", "display_name": "Python 3", "language": "python"},
                       "language_info": {"name": "python"}},
          "cells": []}
    for i, (kind, src) in enumerate(CELLS):
        cell = {"cell_type": kind, "id": f"c{i:02d}", "metadata": {}, "source": src}
        if kind == "code":
            cell.update(outputs=[], execution_count=None)
        nb["cells"].append(cell)
    out = Path(__file__).with_name("finswe_pilot.ipynb")
    out.write_text(json.dumps(nb, indent=1, ensure_ascii=False))
    print(f"wrote {out} ({len(CELLS)} cells)")


if __name__ == "__main__":
    main()
