"""Event study of monthly ex-dividend days for covered-call / income ETFs (raw, unadjusted prices)."""
import json, sys
import numpy as np, pandas as pd, yfinance as yf

OUT = sys.argv[1]
SYMS = ["JEPQ", "JEPI", "QYLD", "SCHD"]
res = {}
for sym in SYMS:
    t = yf.Ticker(sym)
    h = t.history(period="max", auto_adjust=False, actions=True)
    h.index = h.index.tz_localize(None).normalize()
    h = h[["Open", "High", "Low", "Close", "Dividends"]].dropna(subset=["Close"])
    c = h["Close"]; o = h["Open"]
    ret = c.pct_change()
    ema50 = c.ewm(span=50, adjust=False).mean()
    gap = c / ema50 - 1
    ex = h.index[h["Dividends"] > 0]
    rows = []
    for d in ex:
        i = h.index.get_loc(d)
        if i < 60 or i + 15 >= len(h):
            continue
        prev = c.iloc[i - 1]; div = h["Dividends"].iloc[i]
        rows.append({
            "date": d.strftime("%Y-%m-%d"), "div": float(div), "yield": float(div / prev),
            "gap_open": float(o.iloc[i] / prev - 1), "ret_ex": float(c.iloc[i] / prev - 1),
            "drop_over_div": float((prev - o.iloc[i]) / div),
            "pre10": float(c.iloc[i - 1] / c.iloc[i - 11] - 1),
            "post10": float(c.iloc[i + 10] / c.iloc[i] - 1),
            "days_to_recover": next((k for k in range(1, 40) if i + k < len(h) and c.iloc[i + k] >= prev), None),
            "ema_gap_prev": float(gap.iloc[i - 1]), "ema_gap_ex": float(gap.iloc[i]),
            "cross_below_ema": bool(gap.iloc[i - 1] >= 0 > gap.iloc[i]),
            "below_band4": bool(gap.iloc[i] < -0.04),
        })
    ev = pd.DataFrame(rows)
    normal = ret.drop(index=[d for d in ex if d in ret.index], errors="ignore").dropna()
    # average path relative to ex-date (t-15..t+15), cumulative from t-16 close
    paths = []
    for d in ex:
        i = h.index.get_loc(d)
        if 16 <= i < len(h) - 16:
            base = c.iloc[i - 16]
            paths.append((c.iloc[i - 15:i + 16].values / base - 1))
    avg_path = np.mean(paths, axis=0).tolist() if paths else []
    # trading days between ex-dates
    gaps = np.diff([h.index.get_loc(d) for d in ex])
    res[sym] = {
        "n_bars": int(len(h)), "first": h.index[0].strftime("%Y-%m-%d"), "last": h.index[-1].strftime("%Y-%m-%d"),
        "n_exdiv": int(len(ev)),
        "median_trading_days_between_ex": float(np.median(gaps)) if len(gaps) else None,
        "yield_mean": float(ev["yield"].mean()), "yield_p10": float(ev["yield"].quantile(.1)), "yield_p90": float(ev["yield"].quantile(.9)),
        "gap_open_mean": float(ev["gap_open"].mean()), "ret_ex_mean": float(ev["ret_ex"].mean()),
        "ret_ex_median": float(ev["ret_ex"].median()),
        "drop_over_div_median": float(ev["drop_over_div"].median()),
        "normal_day_ret_mean": float(normal.mean()), "normal_day_absret_mean": float(normal.abs().mean()),
        "pre10_mean": float(ev["pre10"].mean()), "post10_mean": float(ev["post10"].mean()),
        "days_to_recover_median": float(ev["days_to_recover"].dropna().median()),
        "recover_within_10d_frac": float((ev["days_to_recover"].fillna(99) <= 10).mean()),
        "cross_below_ema_frac": float(ev["cross_below_ema"].mean()),
        "below_band4_frac": float(ev["below_band4"].mean()),
        "ema_gap_ex_p10": float(ev["ema_gap_ex"].quantile(.1)),
        "avg_path_tminus15_to_tplus15": [round(x, 5) for x in avg_path],
        "last_events": ev.tail(6)[["date", "div", "yield", "ret_ex", "drop_over_div", "days_to_recover", "ema_gap_ex"]].round(4).to_dict("records"),
    }
    h.to_csv(f"{OUT}/{sym}_daily_raw.csv")
json.dump(res, open(f"{OUT}/exdiv_summary.json", "w"), indent=1)
for s, r in res.items():
    print(f"== {s} {r['first']}..{r['last']} bars={r['n_bars']} ex-divs={r['n_exdiv']} spacing={r['median_trading_days_between_ex']}td")
    print(f"   yield/ex mean {r['yield_mean']:.2%} (p10 {r['yield_p10']:.2%}, p90 {r['yield_p90']:.2%}) | open gap {r['gap_open_mean']:+.2%} | ex-day ret mean {r['ret_ex_mean']:+.2%} median {r['ret_ex_median']:+.2%} | drop/div median {r['drop_over_div_median']:.2f}")
    print(f"   normal day ret {r['normal_day_ret_mean']:+.3%} |abs| {r['normal_day_absret_mean']:.2%} | pre10 {r['pre10_mean']:+.2%} post10 {r['post10_mean']:+.2%} | recover median {r['days_to_recover_median']}d, ≤10d {r['recover_within_10d_frac']:.0%}")
    print(f"   ex-day crosses below EMA50 {r['cross_below_ema_frac']:.0%} | ex-day close < EMA50−4% {r['below_band4_frac']:.0%} | ema gap p10 {r['ema_gap_ex_p10']:+.2%}")
