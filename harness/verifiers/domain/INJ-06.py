"""After a take-profit sale, same-day re-buys wait until price < sale × (1 − buffer)."""
import sys; sys.path.insert(0, sys.argv[1])
from kit import Check, Violation, config, engine, qty, run_checks, transport
from ai_trader.client import TossClient

BASE = [100.0] * 65


def set_price(eng, tmp, last):
    eng.client = TossClient(config(tmp), transport=transport({}, BASE + [last]))


def scenario():
    # judged on the rule decision: execution of the follow-up BUY is subject to the risk
    # cooldown, which only ticks in run(); the invariant is about the take-profit rule itself
    eng, paper, tmp = engine(BASE + [126.0], symbols=["005380"], holdings={"005380": (3, 100.0)})
    eng.settings.accumulate = frozenset({"005380"})
    eng.settings.take_profit = frozenset({"005380"})
    eng.settings.take_profit_pct = 0.20
    eng.settings.take_profit_rebuy_buffer = 0.01
    first = eng.step_symbol("005380")["rule"]["action"]
    sold = qty(paper, "005380") == 0
    set_price(eng, tmp, 125.5)
    above = eng.step_symbol("005380")["rule"]["action"]
    set_price(eng, tmp, 124.0)
    below = eng.step_symbol("005380")["rule"]["action"]
    return first == "SELL" and sold, above, below


def no_churn():
    sold, above, _ = scenario()
    if not sold:
        raise RuntimeError("scenario invalid: +26% did not trigger the take-profit sale")
    if above == "BUY":
        raise Violation("rule re-buys the same day at 125.5, above sale 126 × (1 − 1%) = 124.74")


def rebuy_below_allowed():
    sold, above, below = scenario()
    if sold and below != "BUY":
        raise Violation(f"after falling to 124 (< 124.74) the rule says {below}, expected the accumulate BUY")


run_checks([
    Check("D-TP-1", "no same-day re-buy above the sale price band", "005380 cost 100 → sold at 126 (+26%), then 125.5",
          "no re-buy at 125.5", no_churn),
    Check("D-TP-2", "re-buy allowed once price drops below the band", "same day, price 124 (< 126 × 0.99)",
          "accumulate re-buys", rebuy_below_allowed),
])
