# Task candidates (source: ai-trader git history, classified 2026-10-02)

Unit = **bug**, not commit (several incidents were fixed inside `feat:` commits).
`[K]` criterion: (1) observed in live operation per the commit message, (2) code ran
but violated a domain invariant, (3) the invariant is mechanically checkable.

## A. Incident tasks counted in [K] = 14 public (15 incl. FSC-008, excluded with the live path)

| # | Task id | Source | Invariant | Family | Isolation | Status |
|---|---|---|---|---|---|---|
| 1 | FSC-001-core-guard | `ac056ad` | Core holding closes only on a rule SELL | risk | easy | ✅ extracted |
| 2 | FSC-002-covered-call | `9bf847c`ⓐ | Covered-call ETFs are never trend-sold | risk | hard (bundle) | todo |
| 3 | FSC-003-income-etf-run | `036c06a` | Income ETFs use relaxed exits in `run` | risk | easy | ✅ extracted |
| 4 | FSC-004-income-etf-monitor | `0ba0b78` | Same invariant, `monitor` path | risk | easy | ✅ extracted |
| 5 | FSC-005-report-snapshot | `81375dc`ⓑ | Report path = execution path (`_rule_for`) | consistency | medium | todo |
| 6 | FSC-006-regular-hours | `09b028d` | Off-hours sessions excluded when regular-only | temporal | easy | ✅ extracted |
| 7 | FSC-007-nxt-session | `2e5cdec`+`fe5c1c8` | Non-NXT stock open only in regular hours | temporal | easy | ✅ extracted |
| 8 | FSC-008-margin-fallback | `c4c05ea` | Insufficient-margin reject → limit fallback | risk/order | medium | ⛔ excluded (live path) |
| 9 | FSC-009-hybrid-veto | `3014371` | AI veto only with confidence ≥ threshold | llm | easy | ✅ extracted |
| 10 | FSC-010-regime-line | `ba8793a`ⓐ | AI regime line = engine gate period | consistency | hard | todo |
| 11 | FSC-011-priced-in-sign | `ba8793a`ⓑ | A rally never "prices in" bad news | llm | hard | todo |
| 12 | FSC-012-price-report | `28f434b`ⓐ | Price reports excluded from tone count | news/data | hard (bundle) | todo |
| 13 | FSC-013-label-never-empty | `28f434b`ⓑ | Priced-in label non-empty when headlines exist | llm | hard (bundle) | todo |
| 14 | FSC-014-candle-cap | `2609b5d`ⓐ | Candles request ≤ 200 bars | api/numerical | reconstructed | ✅ extracted |
| 15 | FSC-015-stress-proxy | `9bf847c`ⓑ | Stress proxy follows the symbol's market | consistency | hard (bundle) | todo |

Distinct invariants ≈ 12 (#2–#4 share income-ETF protection; #12/#13 share news
labeling). Report per-invariant aggregates alongside per-task ones.

## B. Pending — need confirmation that the bug was actually observed
| Source | Bug |
|---|---|
| `cf2e167` | Market order rejected (VI / auction) → protective stop missed; tick rounding |
| `d2477af` | Donchian label disagrees with the rule trigger |

## C. Real history, outside [K]
| Source | Use |
|---|---|
| `2609b5d`ⓑ revalidate warmup misalignment | dev-found temporal task (provenance: dev) |
| `81375dc`ⓐ emergency stop −12% fixed | excluded — the fix is a policy choice |
| `6203f3f`, `dcb7cb8`, `ac37164` | excluded — tuning / feature additions |
| `d6d3fbc`, `dc3b7a2`, `6d251ba`, `5a663f9` | **control tasks** (no domain invariant) |

## D. Injected (planned, from `~/Downloads/*_validation.py`)
look-ahead (signal i filled at bar i close), future-news leakage, fee omission,
warmup leakage across folds — ~8 tasks, provenance `injected`.

## Extraction notes (from the first 7)
- Hidden tests are the fix commit's own tests (`tests.orig.patch`). Assertions on
  Korean log/note wording were removed in `tests.patch` (FSC-001/003/004/009) because
  they score phrasing, not behavior; originals are kept for provenance.
- FSC-006 is interface-coupled (tests construct `EngineSettings(regular_hours_only=…)`),
  so its issue names the field.
- FSC-014 has no buggy commit (the bug was fixed before commit). The base re-injects
  it via `bug.patch`, and its hidden tests are hand-written, including an
  anti-gaming test (`defense_ma=150` must still fetch ≥155 bars).
- Anti-gaming check: patches that "fix" by disabling the feature fail P2P —
  FSC-009 "AI never vetoes" fails 2 P2P, and FSC-014 "drop the lookback" fails 1.

## Public-release sanitizing (2026-10-03)
`LiveBrokerAdapter` is removed from every snapshot (`finswe.sanitize`). The class becomes a
stub that raises, and top-level tests that reference it are deleted. Raw patches stay as
provenance. `gold.public.patch` / `tests.public.patch` are re-derived as the diff between
the sanitized base and sanitized base+patch, and everything downstream uses them
(snapshots, scoring, selftest, Kaggle export). All 7 extracted tasks remain VALID.
Consequences:
- FSC-008 (`c4c05ea`) and pending `cf2e167` are both about the live adapter's fallback
  logic, so they are excluded. Public [K] = 14.
- `TossClient` order API also disabled (2026-10-03): `orders` / `order_get` / `order_create` /
  `order_cancel` raise, and `_request` refuses any `/api/v1/orders` path (defense in depth).
  Tests calling those methods are removed. `group_for` path-classification tests stay
  (pure function, no request). Audit of all 7 exported snapshots: 5 order stubs each,
  0 order POST calls left, 0 order/live tests. All tasks are still VALID after the rebuild.

## Task set for the paper-grade run (20 tasks, 2026-10-03)
| id | provenance | family | domain verifier |
|---|---|---|---|
| FSC-001 core-guard | incident | risk | ✓ |
| FSC-002 covered-call | incident (reconstructed) | risk | ✓ |
| FSC-003 income-etf-run | incident | risk | ✓ (ex-div sawtooth) |
| FSC-004 income-etf-monitor | incident | risk | ✓ (ex-div sawtooth) |
| FSC-005 report-snapshot | incident (isolated from 81375dc) | consistency | ✓ |
| FSC-006 regular-hours | incident | temporal | ✓ (behavioral, rewritten) |
| FSC-007 nxt-session | incident | temporal | ✓ |
| FSC-009 hybrid-veto | incident | llm-integration | ✓ |
| FSC-014 candle-cap | incident (reconstructed) | api/numerical | ✓ |
| FSC-015 stress-proxy | incident (isolated from 9bf847c) | consistency | ✓ |
| INJ-01 backtest-lookahead | injected | temporal | ✓ |
| INJ-02 backtest-sell-fee | injected | numerical | ✓ |
| INJ-03 future-news | **latent in current code** | temporal | ✓ |
| INJ-04 revalidate-window | dev-found (reconstructed) | temporal | ✓ |
| INJ-05 accumulate-atr-floor | injected | risk | ✓ |
| INJ-06 takeprofit-rebuy | injected | risk | ✓ |
| INJ-07 priced-in-sign | incident regression (injected) | llm-integration | ✓ |
| FSC-C01 ctrlc-exit | control (ops) | – | none by design |
| FSC-C02 monitor-network | control (ops) | – | none by design |
| FSC-C03 closed-log | control (ops) | – | none by design |
Not included (feature-entangled bundles): FSC-010/011 (ba8793a) and FSC-012/013
(28f434b). Their invariants would require building new features. INJ-07 covers the
FSC-011 invariant as a regression task.
