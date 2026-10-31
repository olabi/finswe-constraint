"""run/engine path: income ETFs exit only on a material decline."""
import sys; sys.path.insert(0, sys.argv[1]); sys.path.insert(0, __import__("os").path.dirname(__file__))
from kit import Check, Violation, engine, last_decision, qty, run_checks
from _income import SCENARIOS, avg_for
from ai_trader.strategy import QuantStrategy

SYM = "JEPI"


def make(key):
    closes, tag, expect_sell, _ = SCENARIOS[key]

    def fn():
        avg = avg_for(closes, tag)
        eng, paper, tmp = engine(closes, symbols=[SYM], strategy=QuantStrategy(),
                                 holdings={SYM: (7, avg)}, currency="USD")
        eng.run(max_polls=1)
        rec = last_decision(tmp, SYM)
        sold = qty(paper, SYM) == 0
        if sold != expect_sell:
            raise Violation(f"{'sold' if sold else 'kept'} the position: final={rec.get('final')}, "
                            f"note={str(rec.get('note'))[:140]!r}")
    return fn


run_checks([
    Check(f"D-INC-RUN-{k}", f"run: income ETF {'exits' if s[2] else 'holds'} — {s[3]}",
          f"mode=rule, {SYM} held 7 shares, QuantStrategy, {s[3]}",
          "SELL (position closed)" if s[2] else "HOLD (position kept)", make(k))
    for k, s in SCENARIOS.items()
])
