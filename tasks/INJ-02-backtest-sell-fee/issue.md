# Backtest equity ignores the selling fee

**Observed.** A round trip in `run_backtest` costs only the buy-side fee: final equity is
higher than buy cost + sell proceeds minus both fees, so high-turnover strategies look
better than they are.

**Expected.** Every fill is charged `notional × fee_bps / 10,000`, on the buy **and** the
sell leg, and final equity reflects both.
