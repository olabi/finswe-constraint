# `run` trend-sells income ETFs on a 0.1% dip below EMA50

**Observed.** I hold SCHD and run `ai-trader run`. The close slipped about 0.1% under
its EMA50 and the engine sold the position as a "regime break". Income ETFs
(`INCOME_ETFS`: dividend / covered-call funds) move sideways by design, so
trend-following exits on them are noise. The `monitor` command already handles this
correctly with relaxed criteria; `run` does not.

**Expected.** When the engine evaluates an income ETF it holds, use the same relaxed
exit criteria as `monitor`:
- SELL only if the close is more than **4% below EMA50**, or the position is down
  **10% or more** from its average cost (capital preservation);
- otherwise HOLD, even if the regular trend strategy would exit.

Non-income symbols keep the existing strategy behavior.
