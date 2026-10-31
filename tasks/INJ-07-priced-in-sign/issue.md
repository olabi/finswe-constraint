# Bad news + rising price is labelled "already priced in"

**Observed.** `priced_in_label` told the advisor that negative news was "이미 반영됨"
(already absorbed) for a stock that had just **risen** 19%. The model then treated the bad
news as harmless and leaned toward buying at the high. This is the label the AI relies on
to avoid exactly this sign error.

**Expected.** For negative-dominant headlines, the "already absorbed" label applies only
when the price has **fallen** (change < 0). With change ≥ 0 the label must say the bad news
is not yet absorbed. The positive-news branches are unchanged.
