# `--defense-ma 200` crashes with 400 invalid-request

**Observed (live).** Running `ai-trader run ... --defense-ma 200` fails on the first
poll: the broker API answers `400 invalid-request` to the candles request. Smaller
values such as `--defense-ma 60` work.

**Context.** A single `/api/v1/candles` request accepts at most **200 bars**. The
defense-MA gate needs at least `defense_ma` bars of history to compute its moving
average.

**Expected.**
- No candles request may ask for more than 200 bars.
- Within that limit, the engine should still fetch enough history for the configured
  defense MA (e.g. `--defense-ma 150` must still fetch at least 155 bars).
- With no defense MA configured, the request size is unchanged.
