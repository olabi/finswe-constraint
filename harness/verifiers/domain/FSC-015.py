"""Market-stress siren follows the symbol's own market proxy (KR→069500, US→VOO)."""
import io, contextlib, sys; sys.path.insert(0, sys.argv[1])
from kit import Check, Violation, candles, engine, ok, run_checks

BASE = [80.0 + i * 0.05 for i in range(60)]


def poll_line(symbol, currency, crashing):
    def series(sym):
        if sym in ("069500", "VOO"):
            return [200.0, 186.0] if sym in crashing else [200.0, 200.4]
        return BASE

    routes = {
        "/api/v1/candles": lambda r: ok(candles(series(r.url.params.get("symbol")), currency)),
        "/api/v1/prices": lambda r: ok([{"symbol": r.url.params["symbols"],
                                          "lastPrice": str(series(r.url.params["symbols"])[-1]),
                                          "currency": currency, "timestamp": "2025-12-10T10:00:00+09:00"}]),
    }
    eng, _, _ = engine(BASE, symbols=[symbol], routes=routes, currency=currency)
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        eng.run(max_polls=1)
    return "\n".join(l for l in buf.getvalue().splitlines() if symbol in l)


def us_ignores_kr():
    line = poll_line("AAPL", "USD", {"069500"})
    if "🚨" in line:
        raise Violation(f"KOSPI200 proxy crash flagged a US stock: {line.strip()[-90:]!r}")


def us_flags_us():
    line = poll_line("AAPL", "USD", {"VOO"})
    if "🚨" not in line:
        raise Violation(f"S&P500 proxy (VOO) −7% did not flag a US stock: {line.strip()[-90:]!r}")


def kr_ignores_us():
    line = poll_line("000660", "KRW", {"VOO"})
    if "🚨" in line:
        raise Violation(f"VOO crash flagged a KR stock: {line.strip()[-90:]!r}")


run_checks([
    Check("D-SIREN-1", "US stock ignores a KOSPI200 crash", "AAPL poll, 069500 −7%, VOO flat",
          "no 🚨 on the AAPL line", us_ignores_kr),
    Check("D-SIREN-2", "US stock is flagged by its own market crash", "AAPL poll, VOO −7%, 069500 flat",
          "🚨 on the AAPL line", us_flags_us),
    Check("D-SIREN-3", "KR stock ignores a US crash", "000660 poll, VOO −7%, 069500 flat",
          "no 🚨 on the 000660 line", kr_ignores_us),
])
