# JEPQ market study — ex-dividend sawtooth, index sync, weekly pivots (2026-10-03)

Data: yfinance raw (unadjusted) daily prices + distributions, 2022-05-04..2026-10-02. JEPQ
checked against Toss daily candles (`~/Downloads/dca_1d_cache.json`): 800/800 bars overlap,
median |diff| 0.00%, max 0.22%. Scripts and outputs are in `data/jepq-study/`.

> JEPQ = JPMorgan **Nasdaq** Equity Premium Income ETF, so its underlying is the Nasdaq-100
> (QQQ), not the S&P 500. The S&P 500 sibling is JEPI (vs SPY), reported for comparison.

## 1. Monthly ex-dividend pattern
| | JEPQ | JEPI | QYLD | SCHD (quarterly) |
|---|---|---|---|---|
| ex-dates · spacing | 51 · 21 td | 73 · 21 td | 145 · 20 td | 58 · 63 td |
| distribution / price | 0.94% (p10 0.76, p90 1.18) | 0.71% | 0.92% | 0.79% |
| ex-day return (mean) | −0.90% | −0.64% | −0.87% | −0.90% |
| open gap / distribution | 0.94 | 0.83 | 0.83 | 0.88 |
| 10 d before → 10 d after | +0.35% → +1.10% | +0.15% → +0.57% | +0.31% → +0.33% | −0.04% → +0.64% |
| recovers prior close (median) | 4 d (74% within 10 d) | 3 d | 6 d | 4 d |
| ex-day close falls below EMA50 | 14% (7/51) | 16% | 23% | 17% |
| ex-day close < EMA50 − 4% | 10% | 3% | 9% | 7% |

- **6 of 7** JEPQ ex-day EMA50 breaks disappear when the distribution is added back. A
  trend rule would sell JEPQ on roughly 1 ex-date in 7 purely because of the payout.
- **2 of 51** ex-dates pushed JEPQ across the −4% relaxed band by themselves, so ai-trader's
  current income rule (gold) can still exit on a distribution. This is a candidate
  improvement (dividend-aware comparison on ex-dates); it needs the validate-strategy
  backtest before adoption.
- Over 12-month holds, price-only return averages +8.6% and total return +19.9%. Price-only
  ≤ −10% happened in 2% of windows; total-return ≤ −10% in 0%. A price-only −10% capital
  stop overstates losses for monthly payers.

## 2. Sync with the underlying index
| | JEPQ ↔ QQQ | JEPI ↔ SPY |
|---|---|---|
| daily corr (ex-dates excluded) | **0.962** (63 d rolling min 0.88) | 0.865 (min 0.33) |
| beta · R² | 0.717 · 0.925 | 0.544 · 0.748 |
| monthly capture up / down | 73% / 67% | 62% / 56% |
| EMA50 regime agreement | **95%** | 82% |
| 20 d direction agreement | 95% | 82% |
| ex-day: ETF vs index → idiosyncratic | −0.91% vs +0.09% → **−0.98%** | −0.63% vs +0.20% → −0.74% |
| ex-day EMA50 breaks with the index still above its EMA50 | 4 / 7 | 11 / 12 |
| cumulative: price · total · index | +19% · +96% · +128% | +12% · +93% · +161% |

JEPQ is QQQ at ~0.72× with a monthly, idiosyncratic −1% step. Weekly turning points line
up (§3): JEPQ turns the same week as QQQ or 1–2 weeks later, and the lag shows up mostly at
highs, consistent with capped upside.

### Synthetic data (harness/verifiers/kit.py)
`index_linked_paths` generates QQQ-like index paths and JEPQ = 0.00008 + 0.717·index + ε
(sd 0.29%), plus a −1.04 × distribution step on ex-dates (close-to-close). Fit over 40
paths × 1,108 bars:

| | synthetic | actual |
|---|---|---|
| daily corr | 0.961 | 0.962 |
| beta | 0.715 | 0.717 |
| EMA50 regime agreement | 89% | 95% |
| ex-day ETF return | −0.90% | −0.91% |
| ex-day idiosyncratic | −0.97% | −0.98% |
| ex-day EMA50 breaks | 10% | 14% (n=51) |

Regime agreement is lower because a random walk has less trend persistence than the
market. The new verifier scenario `D-INC-*-exdiv` puts an ex-date drop of −0.93% that takes
JEPQ from +0.59% to −0.33% vs EMA50 while the index is up 0.49% and 0.77% above its own
EMA50. Base (trend rule) flags it; gold holds.

## 3. Weekly pivots (QQQ weekly-close zigzag ≥ 8%) and news around them
News: Google News RSS, date-bounded to pivot day −3..+4, English "Nasdaq stocks" and
Korean "나스닥". Summaries are paraphrased; raw items with links are in
`data/jepq-study/pivot_news.json` (not redistributed; `pivot_news.py` re-collects it).

| Pivot (day) | QQQ | JEPQ turn | next leg | What the news was about |
|---|---|---|---|---|
| High 2022-05-04 | 330.3 | same wk | −11% | Day after the Fed's 50 bp hike: worst day since 2020 (Nasdaq −5%), fears of bigger hikes |
| Low 2022-06-16 | 269.3 | same wk | +20% | Fed 75 bp hike week; Dow below 30k, $9T S&P value erased, recession debate |
| High 2022-08-12 | 330.6 | +1 wk | −21% | Nasdaq "entered a bull market" (+20% off lows); longest weekly win streak since 2021 |
| Low 2022-10-13 | 254.3 | same wk | +12% | Hot CPI → intraday sell-off then a violent reversal; Nasdaq back to 2-year lows |
| High 2022-12-01 | 295.8 | +2 wk | −9% | No clear trigger in the results; general outlook pieces |
| Low 2022-12-28 | 259.7 | +1 wk | +44% | Year-end: worst year since 2008, Nasdaq −33% for 2022 |
| High 2023-07-27 | 384.7 | +1 wk | −10% | Nasdaq-100 special rebalance (big-tech weight), "cheapest hedges since 2008", AI-valuation doubts |
| Low 2023-10-26 | 342.4 | same wk | +44% | Big-tech earnings hit, Nasdaq-100 −2%, S&P into correction, "worst October in 5 years" |
| High 2024-07-05 | 496.6 | +1 wk | −10% | Record highs on Nvidia; five AI names ≈ 36% of the Nasdaq-100 (concentration) |
| Low 2024-09-06 | 448.2 | same wk | +20% | Worst week since Mar 2023, Nvidia-led tech sell-off, waiting on the Fed; "black Monday" fears in KR press |
| High 2025-02-14 | 538.8 | +1 wk | −22% | Meta's record 17-day winning streak; otherwise quiet (structure / listing news) |
| Low 2025-04-04 | 422.7 | +1 wk | +49% | Reciprocal-tariff shock: Nasdaq −6%, bear market confirmed, panic selling |
| High 2025-10-29 | 637.0 | same wk | −11% | Record closes on Nvidia and megacap earnings; Powell: December cut "far from assured" |
| Low 2026-03-27 | 561.6 | +1 wk | +33% | Nasdaq confirmed a correction: Iran crisis / Middle East, oil ~$108, Meta & Micron sell-off |
| High? 2026-10-02 | 754.5 | same wk | ongoing | Record high after softer jobs data cut rate-hike bets (**unconfirmed**: needs an 8% reversal) |

Patterns (descriptive; n = 15, not a tested signal):
- **Lows come with peak-fear headlines**, such as "bear market confirmed", "worst year since
  2008", "correction confirmed", and "worst week since…". The headline confirming the
  damage tends to land at or near the bottom, which matches the earlier contrarian
  intuition that severe bad news can mark a buying zone.
- **Highs come with milestone or euphoric headlines** ("entered a bull market", "record
  high", "record winning streak") or no news at all. Several highs had no identifiable
  trigger in the window.
- The policy hinge (Fed hike or cut odds) shows up at 6 of 15 pivots, and the tariff or
  geopolitical shock at 2 of 15 lows.
- None of this has been validated as a trading rule. Before any use in ai-trader it would
  go through the validate-strategy backtest, and most earlier news/contrarian variants
  were rejected.

## 4. Daily zoom: QQQ daily-close pivots (≥ 7%) with macro context and themed news
Data: `data/jepq-study/daily_pivots.json` (context from ^TNX, ^VIX, CL=F, TLT, DX-Y.NYB) and
`daily_theme_news.json` (Google News, pivot −2..+2 days, themed queries: war/geopolitics,
Fed/rates, Treasury/bonds, Trump/tariffs, inflation/jobs, plus one Korean macro query).
Raw theme counts are **not comparable across time**: index density rises sharply after
2025 and many 2026 queries hit the 100-item cap. The keyword match also over-counts: in
2022–23 the "war" theme is mostly Ukraine background coverage, and pre-2025 "Trump" is
mostly Trump Media / politics. Drivers below are judged from the headlines, not counts.

JEPQ sync on daily bars: **26/33 pivots on the same day as QQQ, 29/33 within ±2 trading days.**

| # | Pivot | 10Y (5d) | VIX (5d) | WTI 5d | Driver(s) read from the headlines |
|---|---|---|---|---|---|
| 1 | H 2022-05-04 | 2.92% (+10bp) | 25 (−20%) | +6% | Fed 50 bp + QT; next day Nasdaq −5% on "bigger hikes" fear — rates |
| 2 | L 2022-05-24 | 2.76% (−21) | 29 (+13%) | −2% | Fed minutes: more 50 bp hikes; yields fall — rates |
| 3 | H 2022-06-02 | 2.91% (+16) | 25 (−13%) | +6% | "Economic hurricane" (Fed + Ukraine war), oil up — rates / war-energy |
| 4 | L 2022-06-16 | 3.31% (+26) | 33 (+26%) | −3% | Fed 75 bp, yield spike — rates |
| 5 | H 2022-08-15 | 2.79% (+3) | 20 (−6%) | −2% | "Nasdaq bull market" headlines, Fed minutes — euphoria / rates |
| 6 | L 2022-10-14 | 4.01% (+13) | 32 (+2%) | −8% | Hot CPI then violent reversal; UK gilt sell-off — inflation / bonds |
| 7 | H 2022-10-25 | 4.11% (+11) | 28 (−7%) | +3% | Hopes the Fed slows hikes — rates |
| 8 | L 2022-11-03 | 4.12% (+19) | 25 (−8%) | −1% | Fed 75 bp + Powell "more hikes" — rates |
| 9 | H 2022-12-01 | 3.53% (−18) | 20 (−3%) | +4% | Powell signals slower hikes; rally peaks on the news — rates |
| 10 | L 2022-12-28 | 3.89% (+20) | 22 (+3%) | +4% | Worst year since 2008; inflation + war recap — year-end |
| 11 | H 2023-02-02 | 3.40% (−10) | 19 (0%) | −6% | Fed 25 bp, "progress on inflation" — rates |
| 12 | L 2023-03-10 | 3.69% (−27) | 25 (+34%) | −4% | SVB collapse; 2y yield's biggest drop since 1987; hot jobs — banking / bonds |
| 13 | H 2023-07-18 | 3.79% (−19) | 13 (−10%) | +1% | Calm (VIX 13), renewed hike worries, yields jump — rates |
| 14 | L 2023-10-26 | 4.84% (−14) | 21 (−3%) | −7% | 10Y near 5% (16-yr high), Alphabet −9%; Israel–Hamas backdrop — bonds / earnings |
| 15 | H 2024-03-22 | 4.22% (−9) | 13 (−9%) | −1% | Fed keeps 3 cuts → records; BoJ ends negative rates — rates |
| 16 | L 2024-04-19 | 4.62% (+12) | 19 (+8%) | −3% | Iran strikes Israel + hawkish Powell — war + rates |
| 17 | H 2024-07-10 | 4.28% (−16) | 13 (+7%) | −1% | Powell testimony, cut bets, soft CPI → rotation; "Trump trade" in bonds — rates |
| 18 | L 2024-08-07 | 3.97% (−14) | 28 (+70%) | −3% | Weak July jobs + yen-carry unwind; Iran-attack fears — jobs / war |
| 19 | H 2024-08-21 | 3.78% (−4) | 16 (0%) | −7% | Jackson Hole "time has come"; −818k payroll revision — rates / jobs |
| 20 | L 2024-09-06 | 3.71% (−16) | 22 (+43%) | −11% | Aug jobs, big-cut debate, Nvidia sell-off — jobs / rates |
| 21 | H 2025-02-19 | 4.54% (0) | 15 (−5%) | −1% | Tariff drive starts to bite; Ukraine ceasefire hopes — Trump |
| 22 | L 2025-04-08 | 4.26% (+11) | 52 (+140%) | −16% | Reciprocal tariffs; bond-market revolt → 90-day pause — Trump / bonds |
| 23 | H 2025-04-09 | 4.40% (+20) | 34 (+56%) | −13% | Pause-day +12% spike (one-day swing high) — Trump |
| 24 | L 2025-04-21 | 4.41% (−9) | 34 (−10%) | +3% | Trump attacks Powell, "sell America", dollar slides — Trump / Fed |
| 25 | H 2025-10-29 | 4.06% (+10) | 17 (−9%) | +3% | FOMC cut + QT end, but Dec cut "far from assured"; 10Y back > 4% — rates |
| 26 | L 2025-11-20 | 4.11% (−1) | 26 (+32%) | +1% | AI-valuation worries after Nvidia; NY Fed's Williams sparks cut bets — rates / AI |
| 27 | H 2026-01-28 | 4.25% (0) | 16 (−3%) | +4% | Trump picks Warsh for Fed (less dovish); Iran-attack worries lift oil — Trump / Fed |
| 28 | L 2026-03-30 | 4.34% (+1) | 31 (+17%) | +17% | Iran war, oil spike; Trump "war will end in weeks" → rally — war / Trump |
| 29 | H 2026-06-02 | 4.46% (−4) | 16 (−7%) | 0% | Strong jobs → hike odds; Iran worries; worst Nasdaq day of the year — rates / war |
| 30 | L 2026-06-10 | 4.54% (+5) | 22 (+38%) | −6% | Inflation + war worries → Trump calls off Iran strikes, peace deal — war / Trump |
| 31 | H 2026-06-15 | 4.47% (−8) | 16 (−14%) | −12% | Iran-deal relief rally → Fed projects a hike — war → rates |
| 32 | L 2026-07-29 | 4.62% (−4) | 21 (+24%) | −3% | Fed "hawkish hold" (5th), yields up, US–Iran escalation — rates / war |
| 33 | H? 2026-10-02 | 5.26% (+8) | 16 (+4%) | −2% | Weak jobs cut rate-hike bets → record; 10Y 5.26% (**unconfirmed**) — jobs / rates |

### What separates highs from lows (16 confirmed each)
| | Highs | Lows |
|---|---|---|
| VIX level · 5 d change | 19.2 · −3% | **27.6 · +27%** |
| VIX ≥ 25 | 3 / 16 | **9 / 16** |
| QQQ 5 d into the pivot | +3.3% | −5.7% |
| 10Y 5 d change | −1.0 bp | +0.1 bp |

- **Rates are the dominant theme** (Fed decisions, minutes, Powell, jobs and CPI as rate
  inputs) at roughly two-thirds of pivots across the whole period.
- **The stock–bond regime flipped.** Into 2022 lows (hiking cycle) the 10Y rose
  +11.4 bp on average (4/5): yields up, stocks down. Into 2023–26 lows it fell −5.1 bp on
  average (rising in only 4/11), so bonds rallied as stocks bottomed. The exception is the
  April 2025 tariff low, when yields rose with stocks falling ("sell America"). That bond
  revolt preceded the pause that marked the bottom.
- **Trump becomes a direct driver from 2025.** He appears at 8 of the last 13 pivots, via
  tariffs, attacks on Powell, the Fed-chair pick, and Iran war/peace statements. Before
  2025, Trump headlines are mostly noise.
- **War**: 2022 Ukraine coverage is background (it acts through oil and inflation). The
  pivot-specific war triggers are Iran–Israel (Apr 2024) and the 2026 Iran war, where
  **de-escalation headlines mark the rebounds** (Mar 31 and Jun 11, 2026).
- **Lows often end on a policy "put" headline**: SVB backstop (Mar 2023), the tariff pause
  (Apr 9, 2025), Williams' cut signal (Nov 21, 2025), "war will end in weeks"
  (Mar 31, 2026), and strikes called off (Jun 11, 2026).
- Descriptive only (n = 33, overlapping themes, headline-density bias). None of this has
  passed the validate-strategy backtest, so it is not a trading rule.

## 5. Where in the monthly cycle is a share cheapest? (JEPQ, 52 cycles)
Price relative to the close on the day before the ex-date (ex−1 = 0):

| day | ex−5 | ex−2 | **ex−1** | **ex** | ex+2 | ex+4 | ex+7 | ex+10 | ex+15 | ex+18 |
|---|---|---|---|---|---|---|---|---|---|---|
| mean | −0.33% | −0.17% | 0 | **−0.91%** | −0.80% | −0.78% | −0.34% | +0.09% | +0.13% | +0.35% |
| median | −0.59% | −0.10% | 0 | −0.78% | −0.51% | −0.50% | +0.06% | +0.46% | +1.03% | +1.39% |

- **ex−1 is the local peak.** The distribution accrues into the price and the days just
  before the ex-date are the most expensive part of the cycle. This matches the earlier
  live mistake of buying at the high on the day before the ex-date.
- Ex-date through ex+4 is the cheapest stretch. Buying on ex+4 rather than later was
  cheaper by +0.46% (vs ex+7, 73% of cycles), +0.90% (vs ex+10, 65%), and +1.16% (vs ex+18,
  73%). The result holds in both 2022–23 and 2024–26.
- **The mechanism is not a timing edge; it is accrual plus drift.** The price re-accrues
  ~0.94% over 21 trading days and drifts up with QQQ, so the earlier one buys after the
  ex-date, the less of that month's accrual one pays for. Practically, this means "invest
  the dividend as soon as it lands", which is the same time-in-market lesson as the ledger.
- Tax-aware: buying at the ex-date close rather than the day before (forgoing a dividend
  that would be 15% withheld) was cheaper by +0.12% on average (58% of cycles). Small.
- Noise: the cross-cycle sd at ex+10 is 2.6%, larger than the ~1% structural gap. In any
  single month the order can flip about 30% of the time.
- Ex-dates fall around the first business day of the month. Cash arrives on the pay date a
  few business days later (check the broker's dividend schedule), i.e. inside the cheap
  ex..ex+4 stretch.

### PMI (added 2026-10-03)
Themed news for PMI was added to every daily pivot (EN: PMI / ISM / purchasing managers /
manufacturing or services index; KO: PMI / 구매관리자지수 / ISM / 제조업·서비스업 지수),
together with an objective flag: is the pivot within ±2 business days of an ISM release?
(Manufacturing is released on the 1st business day, services on the 3rd.)
- **Release proximity is at chance level.** 10/33 pivots (30%; 6 highs, 4 lows) fall within
  ±2 bd of an ISM release, against a base rate of 32% of all business days. The release
  calendar does not explain the turns.
- Most "PMI" hits are non-US releases (China, India, Europe) or ticker noise (Philip Morris
  "PMI", Picard Medical). Korean PMI coverage around pivots is sparse (6 hits in total).
- Where US ISM does appear, it acts as **an input to the rate/inflation story**, never as
  the sole trigger:
  - 2023-02 high: strong services ISM rebound (hot data → rate fears).
  - 2024-08 low: global manufacturing PMI < 50 (growth scare alongside weak jobs).
  - 2026-04 rebound: manufacturing PMI beat.
  - 2026-08: US PMI at an 8-month high with Hormuz delivery delays (supply-shock
    inflation).
  - 2026-10 high: manufacturing ISM slipped (softer data → fewer rate-hike bets).
- Caveat: the keyword regex counts tickers named PMI, so counts are an upper bound. The
  drivers above come from reading the headlines.
