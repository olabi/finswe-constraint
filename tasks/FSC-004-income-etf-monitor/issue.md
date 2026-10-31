# `monitor` raises false SELL alarms for income ETFs

**Observed.** `ai-trader monitor` scans my holdings and fired a SELL alert (plus a
desktop notification) for SCHD when its close was only ~0.1% below EMA50. Income ETFs
(`INCOME_ETFS`) are designed to trade sideways; trend-exit rules (EMA cross,
Donchian, dead cross) are noise for them and these alarms train me to ignore the
monitor.

**Expected.** For held symbols in `INCOME_ETFS`, the monitor should use relaxed
criteria:
- alert SELL only if the close is more than **4% below EMA50**, or the position is
  down **10% or more** from its average cost;
- otherwise report HOLD — no SELL signal and no notification.

Other symbols keep the existing strategy-based alerts.
