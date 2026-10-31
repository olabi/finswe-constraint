"""Write repro/environment.lock.json: everything the runs depended on, pinned.

Run on the machine that holds the Kaggle credentials and the local wheel set (it lists the
Kaggle datasets and hashes the TradingAgents wheels):

  python3 repro/lock_env.py --kaggle ~/miniforge3/envs/kaggle-ps/bin/kaggle \
      --wheels dist/tradingagents-wheels [--ai-trader ~/ai-trader]

The lock records:
- kernel: Kaggle kernel id, machine, Docker image digest, model source, competition and
  dataset sources (pilot/kernel-metadata.json);
- runtime: Python, vLLM and git versions the kernel logged;
- datasets: every file of every attached dataset, with size, as Kaggle lists it now;
- wheels: every TradingAgents wheel with its SHA-256, and the requirements.txt the kernel installs;
- sources: TradingAgents base commit of FinSWE-21; the private benchmark commit and the SHA-256 of
  its uv.lock (the source itself is not released);
- this repository's commit.
"""

from __future__ import annotations

import argparse
import csv
import io
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from reproduce import ROOT, sha256  # noqa: E402

# As logged by the kernel (v10–v13 logs: "python : 3.12.13", "vllm 0.19.1", "git version 2.34.1").
RUNTIME = {"python": "3.12.13", "vllm": "0.19.1", "git": "2.34.1",
           "gpus": "4 × NVIDIA L4, 23034 MiB", "source": "Kaggle kernel log, v10–v13"}


def kaggle_files(kaggle: str, ref: str) -> list[dict]:
    out, token = [], None
    while True:
        cmd = [kaggle, "datasets", "files", ref, "--csv", "--page-size", "200"]
        if token:
            cmd += ["--page-token", token]
        text = subprocess.run(cmd, capture_output=True, text=True, check=True).stdout
        lines = [ln for ln in text.splitlines() if ln and "outdated" not in ln]
        token = next((ln.split("=", 1)[1].strip() for ln in lines if ln.startswith("Next Page Token")), None)
        body = "\n".join(ln for ln in lines if not ln.startswith("Next Page Token"))
        out += [{"name": r["name"], "size": int(r["size"]), "created": r.get("creationDate", "")}
                for r in csv.DictReader(io.StringIO(body))]
        if not token:
            return sorted(out, key=lambda r: r["name"])


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--kaggle", default="kaggle")
    ap.add_argument("--wheels", type=Path, default=ROOT / "dist" / "tradingagents-wheels")
    ap.add_argument("--ai-trader", type=Path, default=ROOT.parent / "ai-trader")
    a = ap.parse_args()

    meta = json.loads((ROOT / "pilot" / "kernel-metadata.json").read_text())
    pub = json.loads((ROOT / "tasks" / "PUB-21-ta-unpadded-date" / "task.json").read_text())
    wheels = sorted(a.wheels.glob("*.whl"))
    if not wheels:
        sys.exit(f"no wheels in {a.wheels}: run harness/public_task.py wheels first")
    uv_lock = a.ai_trader / "uv.lock"
    lock = {
        "generated": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "repository_commit": subprocess.run(["git", "-C", str(ROOT), "rev-parse", "HEAD"],
                                            capture_output=True, text=True).stdout.strip(),
        "kernel": {k: meta[k] for k in ("id", "machine_shape", "enable_gpu", "enable_internet", "docker_image",
                                        "model_sources", "competition_sources", "dataset_sources")},
        "runtime": RUNTIME,
        "datasets": {ref: kaggle_files(a.kaggle, ref) for ref in meta["dataset_sources"]},
        "tradingagents_wheels": {
            "python_tag": "cp312", "count": len(wheels),
            "requirements": (a.wheels / "requirements.txt").read_text().split(),
            "files": [{"name": w.name, "size": w.stat().st_size, "sha256": sha256(w)} for w in wheels]},
        "sources": {
            "finswe21": {"repo": pub["repo"], "base": pub["base"], "fix": pub["fix"]},
            "core_task_bases": {spec["id"]: spec["base"] for spec in (
                json.loads(f.read_text()) for f in sorted((ROOT / "tasks").glob("*/task.json"))) if "repo" not in spec},
            "core_uv_lock_sha256": sha256(uv_lock) if uv_lock.exists() else None},
    }
    out = ROOT / "repro" / "environment.lock.json"
    out.write_text(json.dumps(lock, indent=1, ensure_ascii=False) + "\n")
    print(f"{out.relative_to(ROOT)}: {len(wheels)} wheels, "
          f"{sum(len(v) for v in lock['datasets'].values())} dataset files")
    return 0


if __name__ == "__main__":
    sys.exit(main())
