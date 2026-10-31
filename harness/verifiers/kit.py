"""Shared fixtures for domain verifiers.

Domain verifiers run *inside* the agent's working tree (PYTHONPATH = workdir) so
they exercise the agent's code. They deliberately do NOT reuse the repo's test
helpers or the hidden tests' scenarios: every symbol, price path and threshold
probe here is chosen independently, so passing the verifier is evidence about the
invariant, not about the hidden tests.
"""

from __future__ import annotations

import json
import tempfile
import traceback
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Callable

import httpx

START = datetime(2025, 9, 1, 9, 0)  # hidden tests use 2026-01-01; keep data disjoint


# ── results ───────────────────────────────────────────────────────────────
@dataclass
class Check:
    id: str
    title: str
    scenario: str
    expected: str
    fn: Callable[[], str | None]  # returns observed-on-failure, None on pass


@dataclass
class Outcome:
    id: str
    title: str
    status: str  # pass | fail | error
    scenario: str
    expected: str
    observed: str = ""
    extra: dict = field(default_factory=dict)


class Violation(Exception):
    """Raised by a check when the invariant is violated; message = observation."""


def run_checks(checks: list[Check]) -> None:
    import os

    if os.environ.get("FINSWE_DESCRIBE"):  # A_know / C_know: what is checked, never executed
        print("FINSWE_DESCRIBE " + json.dumps(
            [{"id": c.id, "title": c.title, "scenario": c.scenario, "expected": c.expected}
             for c in checks], ensure_ascii=False))
        return
    out = []
    for c in checks:
        try:
            observed = c.fn()
            status = "pass" if observed is None else "fail"
        except Violation as v:
            status, observed = "fail", str(v)
        except Exception as e:  # agent code crashed or changed an interface
            tb = traceback.format_exc().strip().splitlines()
            status = "error"
            observed = f"{type(e).__name__}: {e} | at {tb[-3].strip() if len(tb) >= 3 else ''}"
        out.append(Outcome(c.id, c.title, status, c.scenario, c.expected, observed or "").__dict__)
    import importlib

    pkg = importlib.import_module(os.environ.get("FINSWE_PKG", "ai_trader"))
    print("FINSWE_RESULTS " + json.dumps({"module": pkg.__file__, "checks": out},
                                          ensure_ascii=False))


# ── market data ───────────────────────────────────────────────────────────
def ok(result) -> httpx.Response:
    return httpx.Response(200, json={"result": result})


def candles(closes: list[float], currency: str = "KRW", spread: float = 0.5) -> dict:
    return {
        "candles": [
            {
                "timestamp": (START + timedelta(days=i)).isoformat() + "+09:00",
                "openPrice": str(c), "highPrice": str(c + spread),
                "lowPrice": str(c - spread), "closePrice": str(c),
                "volume": "5000", "currency": currency,
            }
            for i, c in enumerate(closes)
        ],
        "nextBefore": None,
    }


def ema(values: list[float], n: int) -> float:
    a = 2 / (n + 1)
    e = sum(values[:n]) / n
    for v in values[n:]:
        e = a * v + (1 - a) * e
    return e


# Monthly-distribution calibration (JEPQ vs its underlying index QQQ; yfinance raw prices
# 2022-05..2026-10, 1,108 bars, 51 ex-dates; JEPQ cross-checked against Toss daily candles:
# 800/800 bars, median |diff| 0.00%).
#   JEPQ tracks QQQ: daily corr 0.962 (63d rolling min 0.88), beta 0.717, R² 0.925,
#     monthly capture up 73% / down 67%, EMA50 regime agreement 95%
#   non-ex-day JEPQ return = 0.00008 + 0.717·QQQ + ε, ε sd 0.29%  (alpha includes the
#     distribution accrual; ex accrual the covered-call drag is −0.036%/day)
#   QQQ day: mean +0.084%, sd 1.42% (calm 2023-24: sd 1.13%)
#   ex-date every 21 trading days · distribution 0.94% of price (p10 0.76%, p90 1.18%) ·
#     ex-day JEPQ −0.91% vs QQQ +0.09% → idiosyncratic close-to-close −0.98% ≈ 1.04 × the
#     distribution (the open gap alone is 0.94 ×); drop_ratio uses the close-to-close figure
#   7/51 ex-dates pushed JEPQ below its EMA50; in 4 of them QQQ stayed above its own EMA50
JEPQ_CAL = dict(ex_every=21, dist_yield=0.0094, drop_ratio=1.04, beta=0.717, alpha=0.00008,
                resid_sd=0.0029, idx_mu=0.000838, idx_sd=0.01417)


def index_linked_paths(n: int, start: float = 55.0, idx_start: float = 400.0, *, seed: int,
                       first_ex: int = 15, sd_scale: float = 1.0, **cal
                       ) -> tuple[list[float], list[float], list[int]]:
    """(etf_closes, index_closes, ex_date_indices) for a monthly-distribution ETF that tracks
    an index (JEPQ↔QQQ): etf = alpha + beta·index + ε between ex-dates, and on each ex-date
    the distribution (× drop_ratio) is knocked off the ETF only. Deterministic, stdlib only.
    """
    import random

    c = {**JEPQ_CAL, **cal}
    rng = random.Random(seed)
    etf, idx, ex = [start], [idx_start], []
    for i in range(1, n):
        r_idx = c["idx_mu"] + rng.gauss(0.0, c["idx_sd"] * sd_scale)
        r_etf = c["alpha"] + c["beta"] * r_idx + rng.gauss(0.0, c["resid_sd"] * sd_scale)
        p = etf[-1] * (1 + r_etf)
        if i >= first_ex and (i - first_ex) % c["ex_every"] == 0:
            p -= c["drop_ratio"] * c["dist_yield"] * etf[-1]
            ex.append(i)
        idx.append(round(idx[-1] * (1 + r_idx), 4))
        etf.append(round(p, 4))
    return etf, idx, ex


def monthly_distribution_path(n: int, start: float = 55.0, *, seed: int, first_ex: int = 15,
                              sd_scale: float = 1.0, **cal) -> tuple[list[float], list[int]]:
    """ETF leg of index_linked_paths (closes, ex_date_indices)."""
    etf, _, ex = index_linked_paths(n, start, seed=seed, first_ex=first_ex, sd_scale=sd_scale, **cal)
    return etf, ex


def exdiv_ema_cross(n_min: int = 90, *, gap_lo: float = -0.03, gap_hi: float = -0.002,
                    drop_lo: float = -0.013, drop_hi: float = -0.006, index_healthy: bool = True,
                    seeds: range = range(1, 600), **cal) -> tuple[list[float], dict]:
    """ETF path truncated on an ex-date whose distribution drop alone takes the close from
    at/above EMA50 to just below it, while (index_healthy) the tracked index stays above its
    own EMA50 and is flat-to-up that day (seen on 4/7 JEPQ ex-date EMA breaks)."""
    for seed in seeds:
        etf, idx, ex = index_linked_paths(n_min + 80, seed=seed, **cal)
        for i in ex:
            if i < n_min:
                continue
            g_prev = etf[i - 1] / ema(etf[:i], 50) - 1
            g_cur = etf[i] / ema(etf[:i + 1], 50) - 1
            drop = etf[i] / etf[i - 1] - 1  # JEPQ ex-day return: median −0.77%, mean −0.90%
            idx_gap = idx[i] / ema(idx[:i + 1], 50) - 1
            idx_ret = idx[i] / idx[i - 1] - 1
            if (g_prev >= 0.002 and gap_lo < g_cur < gap_hi and drop_lo <= drop <= drop_hi
                    and (not index_healthy or (idx_gap > 0 and idx_ret >= -0.002))):
                return etf[:i + 1], {"seed": seed, "ex_index": i, "gap_prev": g_prev, "gap_ex": g_cur,
                                     "drop": drop, "index_gap_ema50": idx_gap, "index_ret": idx_ret}
    raise RuntimeError("no ex-date EMA crossing found for the given calibration")


def with_last_vs_ema(base: list[float], ratio: float, n: int = 50) -> list[float]:
    """Append a close that sits at `ratio` × EMA(n) *including* that close."""
    a = 2 / (n + 1)
    e_prev = ema(base, n)
    p = ratio * (1 - a) * e_prev / (1 - ratio * a)
    return base + [round(p, 4)]


def transport(routes: dict[str, Callable[[httpx.Request], httpx.Response]], closes: list[float],
              currency: str = "KRW", spy: list | None = None) -> httpx.MockTransport:
    def handler(req: httpx.Request) -> httpx.Response:
        path = req.url.path
        if path == "/oauth2/token":
            return httpx.Response(200, json={"access_token": "v", "token_type": "Bearer",
                                             "expires_in": 86400})
        for prefix, fn in routes.items():
            if path.startswith(prefix):
                return fn(req)
        if path == "/api/v1/candles":
            if spy is not None:
                spy.append(int(req.url.params.get("count", "0")))
            return ok(candles(closes, currency))
        if path == "/api/v1/prices":
            return ok([{"symbol": req.url.params["symbols"], "lastPrice": str(closes[-1]),
                        "currency": currency, "timestamp": "2025-12-10T10:00:00+09:00"}])
        if path == "/api/v1/exchange-rate":
            return ok({"rate": "1380", "baseCurrency": "USD", "quoteCurrency": "KRW"})
        return httpx.Response(404, json={"error": {"code": "not-found", "message": path}})

    return httpx.MockTransport(handler)


# ── engine construction (only public constructors of the repo) ────────────
def config(tmp: Path):
    from ai_trader.config import Config

    return Config(
        client_id="verifier", client_secret="verifier", account_seq=None,
        base_url="https://verifier.invalid", anthropic_model="x", ollama_model="x",
        ollama_host="http://localhost:1", live_env_enabled=False,
        max_order_krw=5_000_000, max_daily_orders=20, min_confidence=0.65,  # repo default
        max_position_pct=0.5, cooldown_polls=0,
        state_path=str(tmp / "state.json"), decisions_log=str(tmp / "log.jsonl"),
        token_cache_path=str(tmp / "token.json"),
    )


def engine(closes, *, symbols, mode="rule", advisor=None, strategy=None, routes=None,
           settings_kw=None, holdings=None, spy=None, currency="KRW"):
    """Return (engine, paper, tmpdir). holdings = {symbol: (qty, avg)} pre-loaded."""
    from ai_trader.client import TossClient
    from ai_trader.engine import EngineSettings, PaperBrokerAdapter, TradingEngine
    from ai_trader.paper import PaperBroker
    from ai_trader.risk import RiskManager

    tmp = Path(tempfile.mkdtemp(prefix="fsc-verify-"))
    cfg = config(tmp)
    paper = PaperBroker(tmp / "paper.json")
    for sym, (qty, avg) in (holdings or {}).items():
        paper.market_buy(sym, qty, Decimal(str(avg)), currency)
    kw = dict(symbols=symbols, mode=mode, interval="1d", poll_seconds=1,
              max_position_pct=cfg.max_position_pct, max_order_krw=cfg.max_order_krw,
              respect_market_hours=False, decisions_log=str(tmp / "log.jsonl"))
    kw.update(settings_kw or {})
    eng = TradingEngine(
        client=TossClient(cfg, transport=transport(routes or {}, closes, currency, spy)),
        broker=PaperBrokerAdapter(paper),
        risk=RiskManager(max_order_krw=cfg.max_order_krw, max_daily_orders=cfg.max_daily_orders,
                         min_confidence=cfg.min_confidence, cooldown_polls=cfg.cooldown_polls),
        settings=EngineSettings(**kw),
        strategy=strategy,
        advisor=advisor,
    )
    return eng, paper, tmp


def last_decision(tmp: Path, symbol: str | None = None) -> dict:
    rows = [json.loads(x) for x in (tmp / "log.jsonl").read_text(encoding="utf-8").splitlines() if x]
    if symbol:
        rows = [r for r in rows if r.get("symbol") == symbol]
    if not rows:
        raise Violation("no decision was logged")
    return rows[-1]


def qty(paper, symbol) -> float:
    pos = paper.position(symbol)
    return 0.0 if pos is None else float(pos.quantity)


class ScriptedAdvisor:
    """Advisor stub with a fixed answer; accepts any review() signature."""

    def __init__(self, action: str, confidence: float, reasoning: str = "verifier"):
        from ai_trader.advisor import AdvisorDecision

        self.decision = AdvisorDecision(action, confidence, reasoning, 0.1)
        self.calls = 0

    def review(self, *args, **kwargs):
        self.calls += 1
        return self.decision
