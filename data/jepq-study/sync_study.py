"""How closely do JEPQ/JEPI track their underlying index ETFs (QQQ/SPY)?"""
import json, sys
import numpy as np, pandas as pd, yfinance as yf
OUT = sys.argv[1]
PAIRS = [("JEPQ", "QQQ"), ("JEPI", "SPY")]
res = {}
def load(sym):
    h = yf.Ticker(sym).history(period="max", auto_adjust=False, actions=True)
    h.index = h.index.tz_localize(None).normalize()
    return h
for etf, idx in PAIRS:
    a, b = load(etf), load(idx)
    j = a.index.intersection(b.index)
    a, b = a.loc[j], b.loc[j]
    ra, rb = a["Close"].pct_change(), b["Close"].pct_change()          # price returns
    ta = (a["Close"] + a["Dividends"]) / a["Close"].shift() - 1        # total-return day
    df = pd.DataFrame({"ra": ra, "rb": rb, "ta": ta}).dropna()
    exd = set(a.index[a["Dividends"] > 0])
    nx = df[[d not in exd for d in df.index]]
    beta, alpha = np.polyfit(nx["rb"], nx["ra"], 1)
    corr = nx["ra"].corr(nx["rb"])
    roll = nx["ra"].rolling(63).corr(nx["rb"]).dropna()
    # monthly capture (total return for the ETF)
    m = pd.DataFrame({"a": (1 + df["ta"]).resample("ME").prod() - 1, "b": (1 + df["rb"]).resample("ME").prod() - 1})
    up, dn = m[m.b > 0], m[m.b < 0]
    # ex-dates: ETF vs index same day
    exr = df[[d in exd for d in df.index]]
    # EMA50 regime sync
    ea = a["Close"].ewm(span=50, adjust=False).mean(); eb = b["Close"].ewm(span=50, adjust=False).mean()
    above_a = a["Close"] > ea; above_b = b["Close"] > eb
    agree = (above_a == above_b).iloc[60:].mean()
    # ex-day EMA crossings of the ETF: what was the index doing?
    idx_pos = {d: k for k, d in enumerate(a.index)}
    crossings = []
    for d in sorted(exd):
        k = idx_pos.get(d)
        if k is None or k < 60: continue
        if above_a.iloc[k - 1] and not above_a.iloc[k]:
            crossings.append({"date": d.strftime("%Y-%m-%d"), "etf_ret": float(ra.iloc[k]), "idx_ret": float(rb.iloc[k]),
                              "idx_above_ema50": bool(above_b.iloc[k]),
                              "etf_back_above_in_5d": bool(above_a.iloc[k + 1:k + 6].any())})
    r20a, r20b = a["Close"].pct_change(20), b["Close"].pct_change(20)
    sign20 = (np.sign(r20a) == np.sign(r20b)).iloc[60:].mean()
    res[etf] = {
        "index": idx, "overlap": f"{j[0]:%Y-%m-%d}..{j[-1]:%Y-%m-%d} ({len(j)} bars)",
        "corr_daily_ex_exdates": round(float(corr), 3), "beta": round(float(beta), 3),
        "alpha_daily": round(float(alpha), 5), "r2": round(float(corr ** 2), 3),
        "rolling63_corr_min_med": [round(float(roll.min()), 3), round(float(roll.median()), 3)],
        "upside_capture": round(float(up.a.mean() / up.b.mean()), 3),
        "downside_capture": round(float(dn.a.mean() / dn.b.mean()), 3),
        "exday_etf_ret_mean": round(float(exr.ra.mean()), 4), "exday_idx_ret_mean": round(float(exr.rb.mean()), 4),
        "exday_residual_mean": round(float((exr.ra - beta * exr.rb).mean()), 4),
        "ema50_regime_agreement": round(float(agree), 3), "ret20_sign_agreement": round(float(sign20), 3),
        "exday_ema_crossings": crossings,
        "cum_price": round(float(a["Close"].iloc[-1] / a["Close"].iloc[0] - 1), 3),
        "cum_total": round(float((1 + df["ta"]).prod() - 1), 3),
        "cum_index": round(float(b["Close"].iloc[-1] / b["Close"].iloc[0] - 1), 3),
    }
json.dump(res, open(f"{OUT}/sync_summary.json", "w"), indent=1)
for etf, r in res.items():
    print(f"== {etf} vs {r['index']}  {r['overlap']}")
    print(f"   daily corr {r['corr_daily_ex_exdates']} (63d rolling min {r['rolling63_corr_min_med'][0]}, median {r['rolling63_corr_min_med'][1]}) | beta {r['beta']} | R² {r['r2']}")
    print(f"   monthly capture: up {r['upside_capture']:.0%} / down {r['downside_capture']:.0%} | cum: ETF price {r['cum_price']:+.0%}, ETF total {r['cum_total']:+.0%}, index {r['cum_index']:+.0%}")
    print(f"   ex-days: ETF {r['exday_etf_ret_mean']:+.2%} vs index {r['exday_idx_ret_mean']:+.2%} → residual {r['exday_residual_mean']:+.2%}")
    print(f"   EMA50 regime agreement {r['ema50_regime_agreement']:.0%} | 20d direction agreement {r['ret20_sign_agreement']:.0%}")
    c = r["exday_ema_crossings"]
    print(f"   ex-day EMA50 breaks: {len(c)} | index still above its EMA50: {sum(x['idx_above_ema50'] for x in c)} | ETF back above within 5d: {sum(x['etf_back_above_in_5d'] for x in c)}")
