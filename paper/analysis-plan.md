# Analysis plan (pre-registered 2026-10-03, before any multi-seed run)

Procedure follows the evaluation-validity skill (noise floor → one change at a time →
placebo → proof the code path ran → accept/reject). Implemented in `pilot/analyze.py`.
Nothing below is changed after results are seen. Any deviation will be reported as such.

## Conditions (one manipulated variable per contrast)
| condition | invariants stated up front | gate at submit_patch | extra calls after bounce |
|---|---|---|---|
| A_prompt | no | none | – |
| A_know | **yes** | none | – |
| A_retry | no | content-free bounce (once) | +10 |
| B_generic | no | syntax · hygiene · visible-test regressions | +10 per round (≤ 2) |
| C_domain | no | B + domain invariant checks | +10 per round (≤ 2) |
| C_know | **yes** | B + domain invariant checks | +10 per round (≤ 2) |

The invariant statement is generated from the verifier itself (`FINSWE_DESCRIBE` mode:
title / scenario / expected, never observed). A_know therefore knows exactly what C checks.
The system prompt is identical across conditions, and the budget clock starts after prompt
construction.

## Contrasts
- **PRIMARY: C_know vs A_know**: knowing vs enforcing (same knowledge, gate on/off).
- Secondary (Holm-adjusted, supporting only): C_domain vs B_generic (domain vs generic
  feedback), C_domain vs A_retry, B_generic vs A_retry (information vs one more chance),
  A_know vs A_prompt (does stating invariants help alone), A_retry vs A_prompt (does one
  more chance help alone).

## Measurement
- Unit: one (task, condition, seed) run. Outcome: resolved by hidden tests (fresh snapshot;
  env-failing P2P tests excluded and recorded). Contaminated runs (agent touched the
  dataset / verifier paths) are dropped and counted.
- Seeds: 3 (one per kernel version, merged locally). Decoding: temperature 0.2,
  per-request seed.

## Decision rule
- **Noise floor** (min readable delta) = 1.96 · sd_pooled · √(2 / n_seeds), where sd_pooled
  is the pooled SD of per-seed resolve rates across conditions.
- **Placebo**: paired label-swap permutation within (task, seed), 2,000 draws, one-sided p.
- **"X beats Y"** iff diff > noise floor AND placebo p ≤ 0.05 (PRIMARY: raw p; secondary:
  Holm-adjusted p). Otherwise "below noise floor" / "no detectable difference". These are
  never reported as "no effect": the conditions (n tasks, seeds, budget) are always stated.
- 95% CIs are a task-cluster bootstrap (4,000 draws), reported, not gating.

## Pre-run checks (Step 1 / Step 4, asserted in the notebook)
- Complete design (tasks × conditions × seeds), no duplicate runs.
- A_prompt and A_know: the gate never fires. A_know and C_know: the invariant brief is
  present in every prompt (`know_brief_chars > 0`).
- B/C: gate rounds recorded, with errored checks counted separately from violations
  (renamed interfaces etc.).
- Verifier selftest on base (must flag) and gold (must be clean) before export.

## Power (simulation, `analyze.py` rule; baseline 30%, task-difficulty SD 0.25, 3 seeds)
| tasks | false positive (null) | +15 pp | +25 pp | +40 pp |
|---|---|---|---|---|
| 7 | 1% | 16% | 40% | 76% |
| 10 | 1% | 18% | 52% | 80% |
| 20 | 2% | 39% | 74% | 99% |

With the current 7 tasks only a large effect (≈ +40 pp) is reliably detectable. Target is
**≥ 20 tasks** (remaining incident tasks + injected + control tasks) before the
paper-grade run. 7-task runs are reported as pilot evidence.

## Budget (updated 2026-10-03 with v4 timings: ~3.1 min/run)
Per seed: 20 tasks × 6 conditions = 120 runs ≈ 6.3 h wall ≈ 12.6 h quota (L4 counts 2×).
Three seeds ≈ 38 h of quota, more than one week's 30 h. Seeds therefore span two quota
weeks (seed 0 now, seeds 1–2 next). Each seed runs as its own kernel version with
identical config, and results are merged by `analyze.py`.
Control tasks (3) carry no domain verifier: there C_domain/C_know = B_generic. They are
the task-level placebo.
