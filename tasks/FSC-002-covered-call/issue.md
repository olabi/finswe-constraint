# `--trade-income-etf` sold my whole JEPQ position on a trend signal

**Observed (live).** I enabled `trade_income_etf` (`EngineSettings.trade_income_etf = True`)
so the bot could also trend-trade dividend ETFs like SCHD. The next day it sold all 156 shares
of JEPQ because the close slipped under its trend line. JEPQ is a covered-call ETF: it is held
for its monthly distributions, and its price is designed to move sideways, so trend exits
are just noise for it.

**Expected.**
- Covered-call / option-income ETFs (JEPQ, JEPI, QYLD, …) must never be trend-traded. They
  always use the relaxed income-ETF rule (exit only on a material decline or drawdown from
  cost), whether or not `trade_income_etf` is enabled.
- Dividend-growth equity ETFs (SCHD, VYM, HDV, DGRO) keep today's behavior: relaxed rule by
  default, regular trend strategy when `trade_income_etf` is enabled.
