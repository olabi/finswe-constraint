# FinSWE-Constraint

Code, tasks and run records for **Knowing Is Not Enforcing** (`paper/writeup.md`), a pre-registered study of submission-time domain gates for a self-hosted Gemma 4 coding agent (Gemma 4 Developer Agent Paper Track).

## Reproduce the paper's numbers

```bash
python3 repro/reproduce.py
```

This verifies `results/SHA256SUMS` and recomputes every number in Sections 5.1, 5.2 and 5.4 from the run records. It compares each with the printed value (139 values) and redraws Figures 1–4. It needs only the Python standard library. See `repro/README.md`.

## Layout

| Path | Contents |
|---|---|
| `paper/` | the writeup, figures (`figures/make_figures.py`), pre-registered analysis plan, pilot log, verifier design |
| `tasks/` | 20 core tasks (sanitized from a private trading bot) and the public task FinSWE-21 (`PUB-21-ta-unpadded-date`): issue, hidden tests, FAIL_TO_PASS / PASS_TO_PASS lists |
| `harness/` | task build and scoring (`finswe.py`), submission gates and domain verifiers (`feedback.py`, `verifiers/`), selftest (`verify.py`), FinSWE-21 setup (`public_task.py`) |
| `pilot/` | agent runner, system prompt, Kaggle notebook and its builder, pre-registered analysis (`analyze.py`), dataset export |
| `results/` | run records: 360 core runs (`core/v5`, `v6`, `v8`) and 72 FinSWE-21 runs (`v10`–`v13`) |
| `repro/` | `reproduce.py`, checksums, environment lock |
| `data/jepq-study/` | the JEPQ/QQQ calibration study behind the income-ETF verifiers (the collected news headlines are not redistributed; `pivot_news.py` and `daily_theme_news.py` re-collect them) |

Kaggle: notebook `kmmmvs/finswe-constraint-pilot`; datasets `kmmmvs/finswe-pilot-data` (task snapshots, encoded hidden tests, verifiers, runner) and `kmmmvs/finswe-tradingagents-wheels` (offline wheels for FinSWE-21).

## What is not here

- **Gold patches of the 20 core tasks** are withheld, with the core runs' trajectories (a resolved run's patch is a solution), along with the patches that reverse to them (`bug.patch`) and the script that injected those bugs. They are the answers, and keeping them out leaves the benchmark usable. FinSWE-21 ships its gold, which is upstream's public fix (`tasks/PUB-21-ta-unpadded-date/NOTICE`).
- The trading bot's source repository is private. Core tasks ship as sanitized snapshots in the Kaggle dataset: live order paths are stubbed out.
- The competition's harness source (`swegemma`, `adk-eval-core`) comes from Kaggle and is not redistributed.

## License

MIT (`LICENSE`), except `tasks/PUB-21-ta-unpadded-date/gold.patch` and `gold.public.patch`, which are
upstream TradingAgents code under the Apache License 2.0 (see that task's `NOTICE`).
