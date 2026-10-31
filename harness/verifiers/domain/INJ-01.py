"""Backtest has no look-ahead: decision at bar i sees bars ≤ i and fills at bar i+1's open."""
import sys; sys.path.insert(0, sys.argv[1])
from datetime import timedelta
from kit import START, Check, Violation, candles, run_checks
from ai_trader.backtest import run_backtest
from ai_trader.models import Candle
from ai_trader.strategy import RuleSignal


def mk(closes):
    return [Candle.from_api(d) for d in candles(closes)["candles"]]


class Cross:
    name, min_bars = "cross", 8

    def __init__(self, level):
        self.level = level

    def evaluate(self, bars, position):
        if position is None and bars.closes[-1] <= self.level:
            return RuleSignal("BUY", [])
        return RuleSignal("HOLD", [])


def next_open_fill():
    closes = [300.0 - 3 * i for i in range(25)]  # close of bar k = 300 − 3k; open == close in kit candles
    res = run_backtest(Cross(255.0), mk(closes), fee_bps=0.0)
    buy = next((t for t in res.trades if t.side == "BUY"), None)
    if buy is None or buy.price != 252.0:
        raise Violation(f"signal on bar 15 (close 255) filled at {buy.price if buy else None}, expected bar 16 open 252")


def no_future_bar():
    seen = []

    class Spy(Cross):
        def evaluate(self, bars, position):
            seen.append(len(bars.closes))
            return RuleSignal("HOLD", [])

    closes = [50.0 + (i % 4) for i in range(18)]
    run_backtest(Spy(0.0), mk(closes))
    if max(seen) > len(closes) - 1:
        raise Violation(f"strategy saw {max(seen)} of {len(closes)} bars — the final bar can only be a fill bar")


def fill_is_next_open_not_close():
    # kit candles have open == close, so "next open" and "next close" coincide there.
    # Gap every open 1.0 above its close so each candidate fill price is distinct.
    closes = [300.0 - 3 * i for i in range(25)]
    rows = [{"timestamp": (START + timedelta(days=i)).isoformat() + "+09:00",
             "openPrice": str(c + 1.0), "highPrice": str(c + 1.5), "lowPrice": str(c - 0.5),
             "closePrice": str(c), "volume": "5000", "currency": "KRW"} for i, c in enumerate(closes)]
    res = run_backtest(Cross(255.0), [Candle.from_api(d) for d in rows], fee_bps=0.0)
    buy = next((t for t in res.trades if t.side == "BUY"), None)
    names = {256.0: "bar 15 open (look-ahead)", 255.0: "bar 15 close", 252.0: "bar 16 close"}
    if buy is None or buy.price != 253.0:
        got = None if buy is None else f"{buy.price} = {names.get(buy.price, '?')}"
        raise Violation(f"signal on bar 15 (close 255) filled at {got}, expected bar 16 open 253")


run_checks([
    Check("D-LOOK-1", "signal fills at the next bar's open", "falling closes 300→228, BUY when close ≤ 255 (bar 15)",
          "BUY fill price 252 (bar 16 open)", next_open_fill),
    Check("D-LOOK-2", "strategy never sees the bar it trades on", "18-bar oscillating series, spy strategy",
          "max bars seen ≤ 17", no_future_bar),
    Check("D-LOOK-3", "fill uses the next bar's open, not a close", "as D-LOOK-1, every open 1.0 above its close",
          "BUY fill price 253 (bar 16 open)", fill_is_next_open_not_close),
])
