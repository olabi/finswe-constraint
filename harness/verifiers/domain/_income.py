"""Income-ETF exit scenarios shared by FSC-003 (run) and FSC-004 (monitor).

Price paths are index-linked monthly-distribution sawtooths calibrated on JEPQ vs QQQ
(kit.JEPQ_CAL), not smooth trends: the ETF moves ~0.72× its index day to day, and every ~21
trading days knocks ~0.9% off its own price (not the index's). An exit rule must not mistake
that ex-date drop for a breakdown.
"""
from kit import exdiv_ema_cross, monthly_distribution_path, with_last_vs_ema

BASE, _EX = monthly_distribution_path(110, start=48.0, seed=7, sd_scale=0.8)  # calm regime
EXDIV, EXDIV_INFO = exdiv_ema_cross(sd_scale=0.8)

SCENARIOS = {
    # id: (closes, avg_cost_tag, expect_sell, description)
    "micro": (with_last_vs_ema(BASE, 0.982), None, False,
              "close 1.8% below EMA50 (inside the 4% band), cost = close"),
    "exdiv": (EXDIV, None, False,
              f"ex-dividend day: a {EXDIV_INFO['drop']:+.2%} distribution drop takes the close from "
              f"{EXDIV_INFO['gap_prev']:+.2%} to {EXDIV_INFO['gap_ex']:+.2%} vs EMA50 while the tracked "
              f"index stays {EXDIV_INFO['index_gap_ema50']:+.1%} above its own EMA50 (cost = close)"),
    "break": (with_last_vs_ema(BASE, 0.945), None, True,
              "close 5.5% below EMA50 (outside the 4% band), cost = close"),
    "drawdown": (with_last_vs_ema(BASE, 1.002), "dd12", True,
                 "close at EMA50 but 12% under average cost"),
}


def avg_for(closes, tag):
    return round(closes[-1] / 0.88, 4) if tag == "dd12" else closes[-1]
