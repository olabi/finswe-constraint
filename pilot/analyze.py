"""Pre-registered analysis for the FinSWE-Constraint pilot (stdlib only).

Unit of analysis: one (task, condition, seed) run, resolved ∈ {0,1}; contaminated runs dropped.

  rates        per-condition resolve rate, 95% CI by cluster bootstrap over tasks
               (resample tasks with replacement, keep all their seeds)
  paired       X vs Y on matched (task, seed) pairs: mean difference with a task-cluster
               bootstrap CI, discordant counts, exact two-sided McNemar p
  noise floor  min readable delta (evaluation-validity skill, Step 0): seed-level resolve rates
               of each condition are its repeated measurements; their SD is pooled across
               conditions; floor = 1.96 · sd_pooled · sqrt(2 / n_seeds)
  placebo      (Step 3) paired permutation: within each (task, seed) pair the X/Y labels are
               swapped at random, 2,000 times; one-sided p = P(null diff ≥ observed)

Decision rule (fixed before the runs; see paper/analysis-plan.md). PRIMARY contrast is
C_know vs A_know (knowing vs enforcing). "X beats Y" requires diff > min readable delta AND
placebo p ≤ 0.05. Secondary contrasts use Holm-adjusted placebo p and are reported as
supporting evidence only.

Usage: python analyze.py results_v4.jsonl results_v5.jsonl ...  (merged; later files win)
"""

from __future__ import annotations

import itertools
import json
import math
import random
import sys
from collections import defaultdict
from pathlib import Path

B = 4000
ALPHA = 0.05


def load(paths: list[Path]) -> list[dict]:
    rows: dict[tuple, dict] = {}
    for p in paths:
        for line in Path(p).read_text().splitlines():
            if line.strip():
                r = json.loads(line)
                rows[(r["task"], r["condition"], r["seed"])] = r
    return [r for r in rows.values() if not r.get("contaminated")]


def _by(rows, *keys):
    out = defaultdict(list)
    for r in rows:
        out[tuple(r[k] for k in keys)].append(r)
    return out


def _quantiles(xs: list[float]) -> tuple[float, float]:
    xs = sorted(xs)
    lo = xs[int(math.floor(ALPHA / 2 * (len(xs) - 1)))]
    hi = xs[int(math.ceil((1 - ALPHA / 2) * (len(xs) - 1)))]
    return lo, hi


def rates(rows: list[dict], seed: int = 0) -> dict[str, dict]:
    rng = random.Random(seed)
    out = {}
    for (cond,), rs in sorted(_by(rows, "condition").items()):
        per_task = defaultdict(list)
        for r in rs:
            per_task[r["task"]].append(float(r["resolved"]))
        tasks = list(per_task)
        point = sum(sum(v) for v in per_task.values()) / sum(len(v) for v in per_task.values())
        boots = []
        for _ in range(B):
            pick = [per_task[rng.choice(tasks)] for _ in tasks]
            n = sum(len(v) for v in pick)
            boots.append(sum(sum(v) for v in pick) / n)
        lo, hi = _quantiles(boots)
        out[cond] = {"runs": len(rs), "tasks": len(tasks), "seeds": len({r["seed"] for r in rs}),
                     "rate": point, "ci": (lo, hi)}
    return out


def _mcnemar_p(b: int, c: int) -> float:
    """Exact two-sided binomial test on discordant pairs (b: X-only wins, c: Y-only wins)."""
    n = b + c
    if n == 0:
        return 1.0
    k = min(b, c)
    tail = sum(math.comb(n, i) for i in range(0, k + 1)) / 2 ** n
    return min(1.0, 2 * tail)


def paired(rows: list[dict], x: str, y: str, seed: int = 0) -> dict:
    rng = random.Random(seed)
    idx = {(r["task"], r["seed"], r["condition"]): float(r["resolved"]) for r in rows}
    pairs = defaultdict(list)  # task -> list of (x, y)
    for (task, s, cond), v in idx.items():
        if cond == x and (task, s, y) in idx:
            pairs[task].append((v, idx[(task, s, y)]))
    flat = [p for v in pairs.values() for p in v]
    if not flat:
        return {"x": x, "y": y, "pairs": 0}
    diff = sum(a - b for a, b in flat) / len(flat)
    tasks = list(pairs)
    boots = []
    for _ in range(B):
        pick = [p for t in (rng.choice(tasks) for _ in tasks) for p in pairs[t]]
        boots.append(sum(a - b for a, b in pick) / len(pick))
    lo, hi = _quantiles(boots)
    b_ = sum(1 for a, b in flat if a > b)
    c_ = sum(1 for a, b in flat if b > a)
    return {"x": x, "y": y, "pairs": len(flat), "tasks": len(tasks), "diff": diff, "ci": (lo, hi),
            "x_only": b_, "y_only": c_, "mcnemar_p": _mcnemar_p(b_, c_)}


def noise_floor(rows: list[dict], z: float = 1.96) -> dict:
    """Pooled seed-to-seed SD of the resolve rate → minimum readable delta between conditions."""
    per, num, den, n_seeds = {}, 0.0, 0, []
    for (cond,), rs in _by(rows, "condition").items():
        by_seed = defaultdict(list)
        for r in rs:
            by_seed[r["seed"]].append(float(r["resolved"]))
        rates_ = [sum(v) / len(v) for v in by_seed.values()]
        flips = sum(1 for _, rr in _by(rs, "task").items() if len({r["resolved"] for r in rr}) > 1)
        if len(rates_) >= 2:
            m = sum(rates_) / len(rates_)
            var = sum((x - m) ** 2 for x in rates_) / (len(rates_) - 1)
            num += var * (len(rates_) - 1); den += len(rates_) - 1; n_seeds.append(len(rates_))
            per[cond] = {"seed_rates": rates_, "sd": math.sqrt(var), "tasks_flipping_across_seeds": flips}
    if not den:
        return {"per_condition": per, "sd_pooled": None, "floor": None}
    sd = math.sqrt(num / den); n = min(n_seeds)
    return {"per_condition": per, "sd_pooled": sd, "n_seeds": n, "floor": z * sd * math.sqrt(2.0 / n)}


def placebo(rows: list[dict], x: str, y: str, n: int = 2000, seed: int = 0) -> dict:
    """Paired label-swap permutation test (one-sided, X > Y)."""
    rng = random.Random(seed)
    idx = {(r["task"], r["seed"], r["condition"]): float(r["resolved"]) for r in rows}
    pairs = [(v, idx[(t, s, y)]) for (t, s, c), v in idx.items() if c == x and (t, s, y) in idx]
    if not pairs:
        return {"p": None, "n": 0}
    obs = sum(a - b for a, b in pairs) / len(pairs)
    ge = 0
    for _ in range(n):
        d = sum((a - b) if rng.random() < 0.5 else (b - a) for a, b in pairs) / len(pairs)
        ge += d >= obs - 1e-12
    return {"p": ge / n, "n": n, "observed": obs}


def holm(ps: list[float | None]) -> list[float | None]:
    vals = [(p, i) for i, p in enumerate(ps) if p is not None]
    vals.sort()
    out: list[float | None] = [None] * len(ps)
    running = 0.0
    for rank, (p, i) in enumerate(vals):
        running = max(running, min(1.0, (len(vals) - rank) * p))
        out[i] = running
    return out


CONTRASTS = [  # (X, Y, question)
    ("C_know", "A_know", "Knowing ≠ enforcing: same invariant knowledge, gate on vs off"),
    ("C_domain", "B_generic", "Domain vs generic executable feedback"),
    ("C_domain", "A_retry", "Domain feedback vs content-free retry with the same extra budget"),
    ("B_generic", "A_retry", "Generic feedback vs content-free retry"),
    ("A_know", "A_prompt", "Does stating the invariants in the prompt help on its own?"),
    ("A_retry", "A_prompt", "Does one more chance + budget help on its own?"),
]


PRIMARY = ("C_know", "A_know")


def verdict(diff: float | None, p: float | None, floor: float | None) -> str:
    if diff is None:
        return "not run"
    if floor is None:
        return "no noise floor yet (need ≥ 2 seeds) — descriptive only"
    if diff > floor and p is not None and p <= 0.05:
        return "X beats Y"
    if diff <= floor:
        return "below noise floor"
    return "above floor but placebo p > 0.05"


def report(rows: list[dict]) -> str:
    out = [f"valid runs: {len(rows)}", "", "| condition | runs | tasks | seeds | resolve rate | 95% CI (task bootstrap) |",
           "|---|---|---|---|---|---|"]
    for c, r in rates(rows).items():
        out.append(f"| {c} | {r['runs']} | {r['tasks']} | {r['seeds']} | {r['rate']:.1%} | "
                   f"{r['ci'][0]:.1%} – {r['ci'][1]:.1%} |")
    nf = noise_floor(rows)
    out += ["", "noise floor (min readable delta): "
                + (f"{nf['floor']:.1%} (pooled seed sd {nf['sd_pooled']:.1%}, {nf['n_seeds']} seeds)"
                   if nf["floor"] is not None else "n/a (single seed)")]
    for c, v in sorted(nf["per_condition"].items()):
        out.append(f"  {c}: seed rates {[round(x, 3) for x in v['seed_rates']]}, "
                   f"tasks flipping across seeds {v['tasks_flipping_across_seeds']}")
    res = []
    for x, y, q in CONTRASTS:
        pr = paired(rows, x, y)
        pl = placebo(rows, x, y) if pr.get("pairs") else {"p": None}
        res.append((x, y, q, pr, pl))
    adj = holm([pl["p"] if (x, y) != PRIMARY else None for x, y, _, _, pl in res])
    out += ["", "| contrast | role | pairs | diff | 95% CI | X-only / Y-only | placebo p | Holm p | verdict |",
            "|---|---|---|---|---|---|---|---|---|"]
    for (x, y, q, pr, pl), hp in zip(res, adj):
        primary = (x, y) == PRIMARY
        if not pr.get("pairs"):
            out.append(f"| {x} vs {y} | {'PRIMARY' if primary else 'secondary'} | 0 | – | – | – | – | – | not run |")
            continue
        p_used = pl["p"] if primary else hp
        out.append(f"| {x} vs {y} | {'PRIMARY' if primary else 'secondary'} | {pr['pairs']} | {pr['diff']:+.1%} | "
                   f"{pr['ci'][0]:+.1%} – {pr['ci'][1]:+.1%} | {pr['x_only']} / {pr['y_only']} | "
                   f"{pl['p']:.3f} | {'–' if primary else f'{hp:.3f}'} | {verdict(pr['diff'], p_used, nf['floor'])} |")
    return "\n".join(out)


if __name__ == "__main__":
    print(report(load([Path(a) for a in sys.argv[1:]])))
