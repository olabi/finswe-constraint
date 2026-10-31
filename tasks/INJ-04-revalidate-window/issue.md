# Re-validation flags fake edge decay

**Observed.** `ai-trader revalidate` reported an edge as decaying even when variant A and
variant B trade identically. Variants with different warm-up needs (e.g. a 200-bar defense
MA vs none) are scored over different date ranges, so their Sharpe ratios are not
comparable.

**Expected.** In `revalidate_universe`, every A/B comparison must score both variants over
the **same** bar window (the later of the two warm-ups), so two variants that trade the
same way get the same Sharpe.
