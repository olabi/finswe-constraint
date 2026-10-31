"""Daily QQQ zigzag pivots with JEPQ sync and macro context (10Y, VIX, WTI, TLT, DXY)."""
import json, sys
import pandas as pd, yfinance as yf
OUT, TH = sys.argv[1], float(sys.argv[2])
def load(s, start="2022-04-01"):
    h = yf.Ticker(s).history(start=start, auto_adjust=False)
    h.index = h.index.tz_localize(None).normalize(); return h["Close"]
q, j = load("QQQ"), load("JEPQ")
j = j[j.index >= "2022-05-04"]; q = q[q.index >= j.index[0]]
ctx = {k: load(t) for k, t in {"us10y": "^TNX", "vix": "^VIX", "wti": "CL=F", "tlt": "TLT", "dxy": "DX-Y.NYB"}.items()}
if ctx["us10y"].median() > 20: ctx["us10y"] = ctx["us10y"] / 10
def zigzag(c, th):
    v, piv, trend, ext = c.values, [], 0, 0
    for i in range(1, len(v)):
        if trend == 0:
            if v[i] / v[0] - 1 >= th: piv.append((0, "low")); trend, ext = 1, i
            elif 1 - v[i] / v[0] >= th: piv.append((0, "high")); trend, ext = -1, i
        elif trend == 1:
            if v[i] >= v[ext]: ext = i
            elif 1 - v[i] / v[ext] >= th: piv.append((ext, "high")); trend, ext = -1, i
        else:
            if v[i] <= v[ext]: ext = i
            elif v[i] / v[ext] - 1 >= th: piv.append((ext, "low")); trend, ext = 1, i
    piv.append((ext, "high" if trend == 1 else "low"))
    return piv
def at(s, d, k=0):
    s = s[s.index <= d]
    return float(s.iloc[-1 - k]) if len(s) > k else None
pv = zigzag(q, TH); rows = []
for n, (i, kind) in enumerate(pv):
    d = q.index[i]
    win = j[(j.index >= q.index[max(0, i - 5)]) & (j.index <= q.index[min(len(q) - 1, i + 5)])]
    jd = win.idxmax() if kind == "high" else win.idxmin()
    off = int(j.index.get_loc(jd) - j.index.get_loc(d)) if d in j.index else None
    nxt = pv[n + 1][0] if n + 1 < len(pv) else None
    r = {"kind": kind, "day": d.strftime("%Y-%m-%d"), "qqq": round(float(q.iloc[i]), 2),
         "qqq_5d_into": round(float(q.iloc[i] / q.iloc[max(0, i - 5)] - 1), 4),
         "next_leg": round(float(q.iloc[nxt] / q.iloc[i] - 1), 4) if nxt is not None else None,
         "jepq_offset_td": off, "confirmed": n + 1 < len(pv)}
    for k, s in ctx.items():
        now, ago = at(s, d), at(s, d, 5)
        r[k] = round(now, 3) if now is not None else None
        if now is not None and ago:
            r[k + "_5d"] = round((now - ago) * 100, 1) if k == "us10y" else round(now / ago - 1, 4)
    rows.append(r)
json.dump(rows, open(f"{OUT}/daily_pivots.json", "w"), indent=1)
print(f"{len(rows)} pivots (th={TH:.0%})")
for r in rows:
    nl = f"{r['next_leg']:+.1%}" if r["next_leg"] is not None else "ongoing"
    print(f"{r['kind']:<4} {r['day']} QQQ {r['qqq']:>7} 5d {r['qqq_5d_into']:+.1%} next {nl:>7} | JEPQ {r['jepq_offset_td']:+d}td | "
          f"10Y {r['us10y']:.2f}% ({r.get('us10y_5d', 0):+.0f}bp) VIX {r['vix']:.1f} ({r.get('vix_5d', 0):+.0%}) WTI {r.get('wti_5d', 0):+.1%} TLT {r.get('tlt_5d', 0):+.1%} DXY {r.get('dxy_5d', 0):+.1%}")
