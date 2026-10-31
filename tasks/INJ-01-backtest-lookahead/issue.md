# Backtest results look too good — entries land exactly on breakouts

**Observed.** `run_backtest` reports entries that fill at the very bar where the breakout
happens, and returns look implausibly strong compared with live trading.

**Expected.** No look-ahead: the strategy's decision at step *i* may only use bars up to
and including bar *i*, and the resulting order fills at the **open of bar i+1**. A signal
triggered by bar *k*'s close must therefore fill at bar *k+1*'s open, never earlier.
