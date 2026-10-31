# Engine polls stale prices during pre/after-market sessions

**Observed.** My strategies run on daily bars. After the regular close (15:30 KST) the
engine still considers the market "open" because the market calendar lists
pre-market and after-market sessions, so it keeps polling and acting on thin,
stale off-hours prices.

**Expected.** Add a setting **`EngineSettings.regular_hours_only: bool`**
(default `True`).
- When `True`, only the `regularMarket` session counts as open for the market-hours
  gate. Pre-market and after-market sessions are ignored, so the engine waits for the
  next regular open.
- When `False`, all calendar sessions (pre, regular, after) count as open — today's
  behavior.
- Expose it on the `run` CLI as an opt-in flag `--include-extended-hours`, which sets
  `regular_hours_only=False`.
