"""Candles requests never exceed the 200-bar API maximum, yet still cover the defense MA."""
import sys; sys.path.insert(0, sys.argv[1])
from kit import Check, Violation, engine, run_checks

CLOSES = [20.0 + i * 0.02 for i in range(90)]


def counts(defense_ma):
    seen = []
    eng, _, _ = engine(CLOSES, symbols=["005380"], spy=seen)
    eng.settings.defense_ma = defense_ma
    eng.step_symbol("005380")
    if not seen:
        raise RuntimeError("no candles request observed")
    return seen


def cap_just_above():
    seen = counts(199)
    if max(seen) > 200:
        raise Violation(f"defense_ma=199 → candles count={max(seen)} (API rejects > 200)")


def cap_far_above():
    seen = counts(400)
    if max(seen) > 200:
        raise Violation(f"defense_ma=400 → candles count={max(seen)} (API rejects > 200)")


def lookback_preserved():
    seen = counts(120)
    if seen[0] < 125:
        raise Violation(f"defense_ma=120 → candles count={seen[0]}; the MA needs ≥125 bars")


run_checks([
    Check("D-CAP-1", "candles request ≤ 200 when defense MA asks for 204",
          "005380, defense_ma=199", "every candles count ≤ 200", cap_just_above),
    Check("D-CAP-2", "candles request ≤ 200 for an oversized defense MA",
          "005380, defense_ma=400", "every candles count ≤ 200", cap_far_above),
    Check("D-CAP-3", "defense MA lookback still honored under the cap",
          "005380, defense_ma=120", "first candles count ≥ 125", lookback_preserved),
])
