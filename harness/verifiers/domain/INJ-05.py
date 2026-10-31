"""Accumulate capital floor widens with volatility."""
import sys; sys.path.insert(0, sys.argv[1])
from kit import Check, Violation, run_checks
from ai_trader.strategy import Bars, PositionView, accumulate_signal


def bars(closes, spread):
    return Bars(list(closes), [c * (1 + spread) for c in closes], [c * (1 - spread) for c in closes],
                list(closes), [500.0] * len(closes))


def volatile_holds():
    closes = [50.0, 53.5, 48.0, 52.0, 46.5, 51.0, 45.0, 49.0] * 3 + [42.0, 39.5, 38.5]
    s = accumulate_signal(bars(closes, 0.07), PositionView(quantity=4, avg_price=50.0))
    if s.action != "HOLD":
        raise Violation(f"−23% drawdown with ~±7% daily ranges was sold: {s.reasons}")


def calm_sells():
    closes = [50.0 - 0.45 * i for i in range(32)]
    s = accumulate_signal(bars(closes, 0.001), PositionView(quantity=4, avg_price=50.0))
    if s.action != "SELL":
        raise Violation(f"calm −28% slide was not sold (fixed floor must still apply): {s.reasons}")


run_checks([
    Check("D-FLOOR-1", "volatile holding survives a −23% drawdown", "±7% daily range, cost 50 → 38.5",
          "HOLD", volatile_holds),
    Check("D-FLOOR-2", "calm holding still hits the fixed floor", "smooth slide 50 → 36, tiny ATR", "SELL", calm_sells),
])
