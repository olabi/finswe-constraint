"""Build submission.zip for the Kaggle competition gemma-4-developer-agent. Stdlib only.

  python3 competition/build_submission.py --src competition/submission_v2 --out submission.zip
  python3 competition/build_submission.py --sample <path to sample_submission/>   # v1 (needs the LoRA adapters)

The configs and prompts are in competition/submission/. The two LoRA adapters are copied from
the competition's own sample_submission/adapters/ (competition data; not redistributed here).
Before zipping, the script checks what HARNESS_README section 2 says the host compiler enforces:
- exactly one root config;
- allowed file extensions only, and no symlinks;
- every !include resolves inside the submission and contains no '..' or absolute path;
- total size under 3 GiB;
- every agent declares the same base model.
It also checks that no instruction contains '{', because ADK would read it as a session-state
template. This script does not submit anything.
"""

from __future__ import annotations

import argparse
import re
import shutil
import sys
import tempfile
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
SRC = HERE / "submission"
ALLOWED_EXT = {".yaml", ".yml", ".md", ".txt", ".py", ".json", ".safetensors"}
ROOT_NAMES = {"agent.yaml", "agent.yml", "root_agent.yaml", "root_agent.yml"}
MAX_BYTES = 3 * 1024 ** 3
INCLUDE = re.compile(r"!include\s+(\S+)")
MODEL = re.compile(r"^\s*model:\s*(\S+)", re.M)


def check(root: Path) -> list[str]:
    bad = []
    files = [p for p in root.rglob("*") if p.is_file() or p.is_symlink()]
    roots = [p for p in root.iterdir() if p.name in ROOT_NAMES]
    if len(roots) != 1:
        bad.append(f"need exactly one root config, found {[p.name for p in roots]}")
    for p in files:
        rel = p.relative_to(root)
        if p.is_symlink():
            bad.append(f"symlink: {rel}")
        if p.suffix not in ALLOWED_EXT:
            bad.append(f"extension not allowed: {rel}")
        if p.suffix in {".yaml", ".yml"}:
            text = p.read_text(encoding="utf-8")
            for inc in INCLUDE.findall(text):
                target = (p.parent / inc).resolve()
                if inc.startswith("/") or not target.is_relative_to(root.resolve()) or not target.exists():
                    bad.append(f"{rel}: !include {inc} does not resolve inside the submission")
        if p.suffix == ".md" and "{" in p.read_text(encoding="utf-8"):
            bad.append(f"{rel}: contains '{{' (ADK would treat it as a state template)")
    models = {m for p in files if p.suffix in {".yaml", ".yml"} for m in MODEL.findall(p.read_text(encoding="utf-8"))}
    if len(models) != 1:
        bad.append(f"agents must share one base model, found {sorted(models)}")
    adapters = set(re.findall(r"^\s*adapter:\s*(\S+)", "\n".join(
        p.read_text(encoding="utf-8") for p in files if p.suffix in {".yaml", ".yml"}), re.M))
    for a in adapters:
        d = root / "adapters" / a
        if not (d / "adapter_config.json").exists() or not (d / "adapter_model.safetensors").exists():
            bad.append(f"adapter '{a}' is referenced but adapters/{a}/ is incomplete")
    size = sum(p.stat().st_size for p in files if p.is_file())
    if size >= MAX_BYTES:
        bad.append(f"total size {size} bytes is not under 3 GiB")
    return bad


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--src", type=Path, default=SRC, help="submission source (default: competition/submission, v1)")
    ap.add_argument("--sample", type=Path, help="the competition's sample_submission/ (only if the source uses adapters)")
    ap.add_argument("--out", type=Path, default=Path("submission.zip"))
    a = ap.parse_args()
    with tempfile.TemporaryDirectory() as tmp:
        build = Path(tmp) / "submission"
        shutil.copytree(a.src, build)
        if a.sample is not None:
            shutil.copytree(a.sample / "adapters", build / "adapters")
        bad = check(build)
        for b in bad:
            print(f"✗ {b}")
        if bad:
            return 1
        files = sorted(p for p in build.rglob("*") if p.is_file())
        with zipfile.ZipFile(a.out, "w", zipfile.ZIP_DEFLATED) as z:
            for p in files:
                z.write(p, p.relative_to(build).as_posix())
        print(f"✓ {a.out}: {len(files)} files, {a.out.stat().st_size} bytes")
        for p in files:
            print(f"  {p.relative_to(build).as_posix()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
