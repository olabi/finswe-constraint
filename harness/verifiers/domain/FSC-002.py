"""Covered-call ETFs are never trend-sold, even with trade_income_etf; dividend-growth ETFs may be."""
import sys; sys.path.insert(0, sys.argv[1]); sys.path.insert(0, __import__("os").path.dirname(__file__))
from kit import Check, Violation, engine, last_decision, qty, run_checks
from _income import SCENARIOS, avg_for
from ai_trader.strategy import QuantStrategy


def run(symbol, key, flag):
    closes, tag, _, _ = SCENARIOS[key]
    eng, paper, tmp = engine(closes, symbols=[symbol], strategy=QuantStrategy(),
                             holdings={symbol: (9, avg_for(closes, tag))}, currency="USD")
    eng.settings.trade_income_etf = flag
    eng.run(max_polls=1)
    return last_decision(tmp, symbol), qty(paper, symbol)


def covered_call_exdiv():
    rec, q = run("JEPI", "exdiv", True)
    if q != 9:
        raise Violation(f"JEPI (covered call) sold on an ex-dividend dip with trade_income_etf on: "
                        f"rule={rec.get('rule')}, final={rec.get('final')}")


def covered_call_micro():
    rec, q = run("QYLD", "micro", True)
    if q != 9:
        raise Violation(f"QYLD (covered call) trend-sold with trade_income_etf on: rule={rec.get('rule')}")


def covered_call_still_protective():
    rec, q = run("QYLD", "drawdown", True)
    if q != 0:
        raise Violation(f"QYLD 12% under cost was not sold (capital floor must still apply): rule={rec.get('rule')}")


run_checks([
    Check("D-CC-1", "covered-call ETF is not sold on an ex-dividend dip even with trend trading enabled",
          "JEPI held 9 sh, trade_income_etf=True, ex-dividend drop crosses EMA50 (index healthy)",
          "position kept", covered_call_exdiv),
    Check("D-CC-2", "covered-call ETF is not trend-sold with trend trading enabled",
          "QYLD held 9 sh, trade_income_etf=True, close 1.8% under EMA50",
          "position kept", covered_call_micro),
    Check("D-CC-3", "covered-call capital floor still sells",
          "QYLD held 9 sh, trade_income_etf=True, close at EMA50 but 12% under cost",
          "position closed", covered_call_still_protective),
])
