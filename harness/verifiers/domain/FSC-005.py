"""Startup report must show the same rule signal the engine executes (income ETFs and stocks)."""
import io, contextlib, sys; sys.path.insert(0, sys.argv[1]); sys.path.insert(0, __import__("os").path.dirname(__file__))
from kit import Check, Violation, engine, run_checks
from _income import SCENARIOS, avg_for
from ai_trader.strategy import QuantStrategy


def reported_vs_executed(symbol, closes, avg, currency):
    eng, _, _ = engine(closes, symbols=[symbol], strategy=QuantStrategy(),
                       holdings={symbol: (6, avg)} if avg else None, currency=currency)
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        eng.report_once()
    line = next((l for l in buf.getvalue().splitlines() if l.strip().startswith(f"{symbol}:")), "")
    if "| 룰 " not in line:
        raise RuntimeError(f"no rule signal for {symbol} in the startup report: {line!r}")
    reported = line.split("| 룰 ")[1].split()[0]
    executed = eng.step_symbol(symbol)["rule"]["action"]
    return reported, executed


def income_consistent():
    closes, tag, _, _ = SCENARIOS["micro"]
    rep, exe = reported_vs_executed("VYM", closes, avg_for(closes, tag), "USD")
    if rep != exe:
        raise Violation(f"startup report shows {rep} but the engine executes {exe} for VYM")


def stock_consistent():
    closes = [50.0 + i * 0.1 for i in range(70)] + [52.0]
    rep, exe = reported_vs_executed("000660", closes, None, "KRW")
    if rep != exe:
        raise Violation(f"startup report shows {rep} but the engine executes {exe} for 000660")


run_checks([
    Check("D-SNAP-1", "income ETF: startup report signal == executed signal",
          "VYM held 6 sh, monthly-distribution path 1.8% under EMA50, QuantStrategy",
          "report_once rule action == step_symbol rule action", income_consistent),
    Check("D-SNAP-2", "regular stock: startup report signal == executed signal",
          "000660 not held, steady uptrend then a dip, QuantStrategy",
          "report_once rule action == step_symbol rule action", stock_consistent),
])
