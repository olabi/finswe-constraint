"""A/B re-validation scores both variants over the same bar window."""
import sys; sys.path.insert(0, sys.argv[1])
from kit import Check, Violation, run_checks
from ai_trader.revalidate import Edge, Variant, revalidate_universe
from ai_trader.strategy import Bars, RuleSignal


class Hold:
    name = "hold"

    def __init__(self, mb):
        self.min_bars = mb

    def evaluate(self, bars, position):
        return RuleSignal("BUY" if position is None else "HOLD", [])


def same_window():
    closes = [60.0 + i * 0.2 + (3 if i % 11 == 0 else 0) for i in range(220)]
    b = Bars(closes, [c + 0.5 for c in closes], [c - 0.5 for c in closes], closes, [1e3] * 220)
    r = revalidate_universe({"Y": b, "Z": b}, edges=[Edge("eq", Variant(Hold(20)), Variant(Hold(20), defense_ma=120))],
                            recent=60)["edges"][0]
    if (r["full_a"], r["recent_a"]) != (r["full_b"], r["recent_b"]):
        raise Violation(f"identical trading scored differently: A {r['full_a']}/{r['recent_a']} vs B {r['full_b']}/{r['recent_b']}")


run_checks([Check("D-WIN-1", "identical behaviour → identical score", "always-in A (warm 20) vs B (defense_ma 120, never binding)",
                  "full and recent Sharpe equal", same_window)])
