"""NXT support: non-NXT KR stocks are open only in regular hours — decided per symbol."""
import sys; sys.path.insert(0, sys.argv[1]); sys.path.insert(0, __import__("os").path.dirname(__file__))
import httpx
from kit import Check, Violation, engine, ok, run_checks
from _calendar import kr, labels

CLOSES = [70.0 + (i % 5) * 0.4 for i in range(70)]
NXT = {"035420": True, "000660": False, "373220": False}


def stocks(req):
    syms = req.url.params.get("symbols", "").split(",")
    return ok([{"symbol": s, "name": "v", "koreanMarketDetail": {"nxtSupported": NXT.get(s, True)}}
               for s in syms if s])


def make_engine(stocks_route=stocks):
    eng, _, _ = engine(CLOSES, symbols=list(NXT),
                       routes={"/api/v1/market-calendar/": lambda r: ok(kr()),
                               "/api/v1/stocks": stocks_route},
                       settings_kw={"regular_hours_only": False, "respect_market_hours": True})
    return eng


def non_nxt_regular_only():
    got = labels(make_engine()._sessions_for("373220"))
    if got != ["regularMarket"]:
        raise Violation(f"373220 (nxtSupported=false) open sessions = {got}")


def no_leak_nxt_first():
    eng = make_engine()
    a = labels(eng._sessions_for("035420"))
    b = labels(eng._sessions_for("000660"))
    if b != ["regularMarket"] or len(a) < 3:
        raise Violation(f"035420(nxt)={a}, then 000660(non-nxt)={b}")


def no_leak_non_nxt_first():
    eng = make_engine()
    b = labels(eng._sessions_for("000660"))
    a = labels(eng._sessions_for("035420"))
    if len(a) < 3:
        raise Violation(f"000660(non-nxt)={b}, then 035420(nxt)={a} — restriction leaked across symbols")


def lookup_failure_no_restriction():
    eng = make_engine(lambda r: httpx.Response(503, json={"error": {"code": "unavailable"}}))
    got = labels(eng._sessions_for("035420"))
    if len(got) < 3:
        raise Violation(f"stocks lookup failed (503) and sessions were restricted to {got}")


run_checks([
    Check("D-NXT-1", "non-NXT stock is regular-hours only even with extended hours on",
          "373220 nxtSupported=false, regular_hours_only=False, KR calendar pre/regular/after",
          "open sessions == ['regularMarket']", non_nxt_regular_only),
    Check("D-NXT-2", "NXT result must not leak (NXT stock queried first)",
          "same engine: 035420 (nxt) then 000660 (non-nxt)",
          "035420 keeps extended sessions; 000660 regular only", no_leak_nxt_first),
    Check("D-NXT-3", "NXT result must not leak (non-NXT stock queried first)",
          "same engine: 000660 (non-nxt) then 035420 (nxt)",
          "035420 still keeps extended sessions", no_leak_non_nxt_first),
    Check("D-NXT-4", "metadata lookup failure adds no restriction",
          "/api/v1/stocks returns 503, regular_hours_only=False",
          "all calendar sessions remain", lookup_failure_no_restriction),
])
