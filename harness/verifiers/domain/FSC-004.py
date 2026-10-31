"""monitor path: income ETFs alert only on a material decline."""
import io, contextlib, sys; sys.path.insert(0, sys.argv[1]); sys.path.insert(0, __import__("os").path.dirname(__file__))
import tempfile
from pathlib import Path
from kit import Check, Violation, config, ok, run_checks, transport
from _income import SCENARIOS, avg_for
from ai_trader import cli
from ai_trader.client import TossClient
from ai_trader.strategy import QuantStrategy

SYM = "VYM"


def make(key):
    closes, tag, expect_sell, _ = SCENARIOS[key]

    def fn():
        avg = avg_for(closes, tag)
        routes = {
            "/api/v1/accounts": lambda r: ok([{"accountNo": "9-9", "accountSeq": 9,
                                               "accountType": "BROKERAGE"}]),
            "/api/v1/holdings": lambda r: ok({"items": [{
                "symbol": SYM, "name": "verifier", "quantity": "12",
                "averagePurchasePrice": str(avg), "lastPrice": str(closes[-1]),
                "currency": "USD", "marketCountry": "US"}]}),
        }
        cfg = config(Path(tempfile.mkdtemp(prefix="fsc-mon-")))
        client = TossClient(cfg, transport=transport(routes, closes, "USD"))
        pings = []
        cli._desktop_notify = lambda t, m: pings.append(t)
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            n = cli._scan_holdings(cfg, client, QuantStrategy(), "1d", True, {})
        alerted = n > 0 or bool(pings)
        if alerted != expect_sell:
            line = next((l for l in buf.getvalue().splitlines() if SYM in l), "")[:160]
            raise Violation(f"sell_count={n}, notifications={len(pings)}; output: {line!r}")
    return fn


run_checks([
    Check(f"D-INC-MON-{k}", f"monitor: income ETF {'alerts' if s[2] else 'stays quiet'} — {s[3]}",
          f"monitor scan, {SYM} held 12 shares, QuantStrategy, notify on, {s[3]}",
          "SELL alert" if s[2] else "no SELL alert and no notification", make(k))
    for k, s in SCENARIOS.items()
])
