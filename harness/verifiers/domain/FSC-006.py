"""regular_hours_only: extended sessions must not count as open (checked via the public gate)."""
import sys; sys.path.insert(0, sys.argv[1]); sys.path.insert(0, __import__("os").path.dirname(__file__))
from datetime import datetime, timedelta, timezone
from kit import Check, Violation, engine, ok, run_checks
from _calendar import kr, us

CLOSES = [30.0 + (i % 7) * 0.3 for i in range(70)]
KST = timezone(timedelta(hours=9))


def opened_at(symbol, cal, regular_only, currency, when):
    import ai_trader.engine as eng

    class Frozen(eng.datetime):
        @classmethod
        def now(cls, tz=None):
            return when.astimezone(tz) if tz else when.replace(tzinfo=None)

    eng.datetime = Frozen
    e, _, _ = engine(CLOSES, symbols=[symbol], currency=currency,
                     routes={"/api/v1/market-calendar/": lambda r: ok(cal),
                             "/api/v1/stocks": lambda r: ok([{"symbol": symbol, "name": "v",
                                 "koreanMarketDetail": {"nxtSupported": True}}])},
                     settings_kw={"regular_hours_only": regular_only, "respect_market_hours": True})
    return e.open_symbols()[0]


US_AFTER = datetime(2025, 11, 25, 7, 0, tzinfo=KST)    # US after-market of the 11-24 session
US_REG = datetime(2025, 11, 25, 1, 0, tzinfo=KST)      # US regular session
KR_AFTER = datetime(2025, 11, 24, 17, 0, tzinfo=KST)   # KR after-market (15:40–20:00)


def us_after_closed():
    got = opened_at("MSFT", us(), True, "USD", US_AFTER)
    if got:
        raise Violation(f"MSFT counted as open during the after-market session: open_symbols → {got}")


def kr_after_closed():
    got = opened_at("000660", kr(), True, "KRW", KR_AFTER)
    if got:
        raise Violation(f"000660 counted as open during the after-market session: open_symbols → {got}")


def extended_opt_in_open():
    got = opened_at("MSFT", us(), False, "USD", US_AFTER)
    if got != ["MSFT"]:
        raise Violation(f"with extended hours enabled, after-market should be open: open_symbols → {got}")


def regular_still_open():
    got = opened_at("MSFT", us(), True, "USD", US_REG)
    if got != ["MSFT"]:
        raise Violation(f"regular session must stay open with regular_hours_only: open_symbols → {got}")


run_checks([
    Check("D-HOURS-1", "US stock: regular-only treats the after-market as closed",
          "MSFT, US calendar, regular_hours_only=True, time = US after-market (07:00 KST)",
          "open_symbols() == []", us_after_closed),
    Check("D-HOURS-2", "KR stock: regular-only treats the after-market as closed",
          "000660, KR calendar, regular_hours_only=True, time = 17:00 KST (after-market)",
          "open_symbols() == []", kr_after_closed),
    Check("D-HOURS-3", "extended-hours opt-in keeps the after-market open",
          "MSFT, US calendar, regular_hours_only=False, time = US after-market",
          "open_symbols() == ['MSFT']", extended_opt_in_open),
    Check("D-HOURS-4", "regular session stays open under regular-only",
          "MSFT, US calendar, regular_hours_only=True, time = US regular session (01:00 KST)",
          "open_symbols() == ['MSFT']", regular_still_open),
])
