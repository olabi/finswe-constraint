"""Write results/SHA256SUMS for every run record and trace archive under results/.

  python3 repro/checksums.py          # rewrite results/SHA256SUMS (sha256sum format)
  sha256sum -c results/SHA256SUMS     # or: python3 repro/reproduce.py, which verifies it first
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from reproduce import ROOT, sha256  # noqa: E402

PATTERNS = ("results.jsonl", "analysis.md", "traces.zip", "first-round-errors.md")


def main() -> int:
    files = sorted(p for p in (ROOT / "results").rglob("*") if p.is_file() and p.name in PATTERNS)
    lines = [f"{sha256(p)}  {p.relative_to(ROOT).as_posix()}" for p in files]
    (ROOT / "results" / "SHA256SUMS").write_text("\n".join(lines) + "\n")
    print(f"{len(lines)} files → results/SHA256SUMS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
