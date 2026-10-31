"""Backtest equity charges the fee on both legs."""
import sys; sys.path.insert(0, sys.argv[1])
from kit import Check, Violation, candles, run_checks
from ai_trader.backtest import run_backtest
from ai_trader.models import Candle
from ai_trader.strategy import RuleSignal


class Swing:
    name, min_bars = "swing", 6

    def evaluate(self, bars, position):
        n = len(bars.closes)
        if position is None and n in (7, 15):
            return RuleSignal("BUY", [])
        if position is not None and n in (11, 19):
            return RuleSignal("SELL", [])
        return RuleSignal("HOLD", [])


def two_round_trips():
    closes = [80.0 + (i % 5) * 1.5 for i in range(24)]
    res = run_backtest(Swing(), [Candle.from_api(d) for d in candles(closes)["candles"]],
                       initial_cash=500_000.0, fee_bps=40.0)
    cash = 500_000.0
    for t in res.trades:
        notional = t.price * t.quantity
        cash += -notional * (1 + 40 / 1e4) if t.side == "BUY" else notional * (1 - 40 / 1e4)
    if abs(res.final_equity - cash) > 1e-6 * cash:
        raise Violation(f"final equity {res.final_equity:,.2f} vs fee-on-both-legs {cash:,.2f}")


run_checks([Check("D-FEE-1", "both fills pay the fee", "two round trips, fee_bps=40",
                  "final equity == cash after fees on every buy and sell", two_round_trips)])
