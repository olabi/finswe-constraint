"""Weekly zigzag pivots of QQQ (driver) and whether JEPQ turns the same week."""
import json, sys
import pandas as pd, yfinance as yf
OUT = sys.argv[1]; TH = float(sys.argv[2]) if len(sys.argv) > 2 else 0.08
def load(s):
    h = yf.Ticker(s).history(period="max", auto_adjust=False, actions=True)
    h.index = h.index.tz_localize(None).normalize(); return h
q, j = load("QQQ"), load("JEPQ")
start = j.index[0]; q = q[q.index >= start]
def weekly(h):
    return h.resample("W-FRI").agg({"High": "max", "Low": "min", "Close": "last"}).dropna()
def zigzag(w, th):
    """Zigzag on weekly closes: a pivot is confirmed after a >= th reversal in closes."""
    c = w["Close"].values
    piv, trend, ext_i = [], 0, 0
    for i in range(1, len(c)):
        if trend == 0:
            if c[i] / c[0] - 1 >= th: piv.append((0, "low")); trend, ext_i = 1, i
            elif 1 - c[i] / c[0] >= th: piv.append((0, "high")); trend, ext_i = -1, i
        elif trend == 1:
            if c[i] >= c[ext_i]: ext_i = i
            elif 1 - c[i] / c[ext_i] >= th: piv.append((ext_i, "high")); trend, ext_i = -1, i
        else:
            if c[i] <= c[ext_i]: ext_i = i
            elif c[i] / c[ext_i] - 1 >= th: piv.append((ext_i, "low")); trend, ext_i = 1, i
    piv.append((ext_i, "high" if trend == 1 else "low"))
    return piv
wq, wj = weekly(q), weekly(j)
rows = []
pv = zigzag(wq, TH)
for n, (i, kind) in enumerate(pv):
    wk = wq.index[i]
    days = q.loc[wk - pd.Timedelta(days=6):wk]
    day = (days["High"].idxmax() if kind == "high" else days["Low"].idxmin())
    price = float(days["High"].max() if kind == "high" else days["Low"].min())
    # JEPQ: extreme within ±2 weeks of the QQQ pivot week
    win = wj.loc[wk - pd.Timedelta(weeks=2):wk + pd.Timedelta(weeks=2)]
    jk = (win["High"].idxmax() if kind == "high" else win["Low"].idxmin()) if len(win) else None
    lag = int((jk - wk).days / 7) if jk is not None else None
    nxt = pv[n + 1][0] if n + 1 < len(pv) else None
    move = None
    if nxt is not None:
        move = float(wq["Close"].iloc[nxt] / wq["Close"].iloc[i] - 1)
    jprice = float(j.loc[day, "Close"]) if day in j.index else None
    rows.append({"kind": kind, "week_end": wk.strftime("%Y-%m-%d"), "day": day.strftime("%Y-%m-%d"),
                 "qqq": round(price, 2), "jepq_close": round(jprice, 2) if jprice else None,
                 "jepq_pivot_week_offset": lag, "move_to_next_pivot": round(move, 4) if move is not None else None,
                 "confirmed": n + 1 < len(pv)})
json.dump(rows, open(f"{OUT}/weekly_pivots.json", "w"), indent=1)
for r in rows:
    mv = f"{r['move_to_next_pivot']:+.1%}" if r["move_to_next_pivot"] is not None else "(ongoing)"
    print(f"{r['kind']:<4} {r['day']} QQQ {r['qqq']:>7} JEPQ {r['jepq_close']} | JEPQ pivot offset {r['jepq_pivot_week_offset']:+d}w | next leg {mv}{'' if r['confirmed'] else '  [unconfirmed]'}")
