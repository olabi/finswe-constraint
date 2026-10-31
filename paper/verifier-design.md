# Feedback verifiers — design and validation (2026-10-02)

## Levels = experimental conditions
| Level | Checks | Condition |
|---|---|---|
| generic | G-SYNTAX (changed .py compile) · G-HYGIENE (non-empty, existing tests untouched, no stray files) · G-REGRESSION (repo's own visible tests) | B |
| domain | per-task invariant checks, `harness/verifiers/domain/FSC-xxx.py` | added in C |

Failures are returned to the agent as `scenario / expected / observed`. A crash
inside the agent's code (e.g. a renamed interface) is reported as `ERROR` with the
exception, not hidden.

## Disjointness from scoring (anti-circularity)
- Hidden tests (`tasks/*/tests.patch`) are never executed by `verify.py`.
- Domain checks never import the repo's test helpers. They use their own mock
  transport, start date (2025-09 vs 2026-01), symbols, price paths and thresholds.

| Task | Hidden tests probe | Feedback probes (different) |
|---|---|---|
| FSC-001 | 005930, golden cross, AI SELL@0.85, 10 sh | 000660 uptrend AI SELL@0.95; non-core 035720 liveness; core −42% floor exit |
| FSC-003/004 | SCHD/JEPQ flat 100 → 99.9 / 95 | JEPI/VYM slow grind; −1.8% (hold), −5.5% (sell), −12% vs cost (sell) |
| FSC-006 | KR 005930 sessions | US MSFT incl. dayMarket; KR 000660; extended opt-in |
| FSC-007 | 005935 non-NXT | 373220 non-NXT; **cross-symbol cache leak both orders**; 503 lookup failure |
| FSC-009 | AI HOLD@0.32 | AI HOLD@0.55 / 0.75 / **0.60 boundary** / agreement |
| FSC-014 | defense 200 / 150 / 0 | defense 199 / 400 / 120 |

Some feedback probes check properties the hidden tests do not: FSC-007 cache leak,
the FSC-009 inclusive boundary, and the FSC-001 non-core liveness on a different
path. This lets us later measure both directions of disagreement: verifier pass
with hidden fail, and the reverse.

## Validation (selftest: must flag base, must be clean on gold)
| Task | Base flagged | Gold |
|---|---|---|
| FSC-001 | D-CORE-1 | clean |
| FSC-003 | D-INC-RUN-micro | clean |
| FSC-004 | D-INC-MON-micro | clean |
| FSC-006 | D-HOURS-1/2/3 (base lacks the setting → ERROR with TypeError) | clean |
| FSC-007 | D-NXT-1/2 | clean |
| FSC-009 | D-VETO-1 | clean |
| FSC-014 | D-CAP-1/2 | clean |

"Gold clean" covers the generic level too: gold passes the visible suite.

## Gaming probes
| Patch | Generic (B) | Domain (C) | Hidden scoring |
|---|---|---|---|
| FSC-009 "AI never vetoes" | caught (visible test) | caught (D-VETO-2/3) | unresolved |
| FSC-014 `count = min(candle_count, 200)` | **passes all 3** | caught (D-CAP-3) | unresolved |

FSC-014 is the paper's thesis in one task: generic executable feedback accepts a
patch that silently disables the domain feature; only the domain constraint
surfaces it.

## Known limitations
- Domain checks call some private methods (`_sessions_for`, `cli._scan_holdings`)
  that exist at base. An agent that renames them gets an ERROR. That is still
  informative feedback, but it should be tracked separately in the analysis.
- One verifier per task (7). Invariants shared across tasks (income-ETF: 003/004)
  share scenarios via `_income.py`.
- Latent bug found while writing FSC-014 probes: the HTF confirmation request
  (`count=self.settings.candle_count`) is uncapped, even in gold. It only bites if
  `candle_count > 200` (default 120), so it is not probed. It is a candidate for a
  new injected/real task.
