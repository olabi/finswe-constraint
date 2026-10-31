# Accumulate mode stops out of volatile holdings on ordinary swings

**Observed.** In `--accumulate` mode a high-volatility holding was sold at about −21%
from cost during a routine swing, although accumulate mode is meant to sell only on a
*wide* capital floor.

**Expected.** The accumulate capital floor must adapt to volatility:
floor = max(stop_pct, atr_mult × ATR / price). A volatile stock (large ATR%) gets a wider
floor than `stop_pct`; a calm one keeps `stop_pct`.
