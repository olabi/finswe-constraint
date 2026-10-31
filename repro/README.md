# Reproducing the paper's numbers

| Command | What it does |
|---|---|
| `python3 repro/reproduce.py` | Verifies `results/SHA256SUMS`, recomputes every number in Sections 5.1, 5.2 and 5.4 of `paper/writeup.md` from the run records, compares each with the printed value (`repro/expected.json`), redraws the figures, and writes `repro/report.md`. Exit 0 only if everything matches. Stdlib only. |
| `python3 repro/checksums.py` | Rewrites `results/SHA256SUMS` (sha256sum format; `sha256sum -c results/SHA256SUMS` also verifies it). |
| `python3 repro/lock_env.py --kaggle <cli> --wheels dist/tradingagents-wheels` | Writes `repro/environment.lock.json`: kernel image digest, model and dataset sources, every dataset file, every TradingAgents wheel with its SHA-256, and the source commits. Needs Kaggle credentials. |

Run records:

| Path | Runs |
|---|---|
| `results/core/v5`, `v6`, `v8` | the 360 core runs (20 tasks × 6 arms), seeds 0, 1, 2; kernel versions of `kmmmvs/finswe-constraint-pilot` |
| `results/v10`–`v13` | the 72 FinSWE-21 runs (6 arms × 3 seeds × 4 kernels) |

Each kernel directory holds `results.jsonl` (one record per run) and `analysis.md` (the kernel's own pre-registered report; kernel v5 wrote none). The core runs' trajectories are withheld: a resolved run's patch is a solution to a task whose gold is withheld. Old versions' outputs come from the Kaggle API with `version_label="v5"` (the CLI's `kernels output` always returns the latest version).
