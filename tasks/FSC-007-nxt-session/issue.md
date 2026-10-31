# Stocks without extended-hours trading are treated as open after 15:30

**Observed.** With extended hours enabled (`regular_hours_only=False`), the engine
treats every KR stock as open during pre/after-market sessions. But only some KR
stocks trade on the extended venue (NXT). For example, my preferred share (005935)
has no NXT listing, so after 15:30 the engine polls a price that cannot trade.

**Expected.**
- For a KR symbol whose stock metadata reports `nxtSupported = false` (the
  `/api/v1/stocks` response, `koreanMarketDetail.nxtSupported`), only the
  `regularMarket` session counts as open, regardless of `regular_hours_only`.
- NXT-supported KR stocks keep the extended sessions when extended hours are enabled.
- If the metadata lookup fails, do not add any extra restriction.
- The decision is per symbol: one symbol's result must not leak into another symbol of
  the same country.
