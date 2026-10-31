"""Figures for paper/writeup.md, written as plain SVG (stdlib only).

Figures 1–2 use the writeup's own tables (Section 5.1). Figures 3–4 are recomputed here from
results/v10–v13 (Section 5.4), so a figure can never drift from the text it illustrates.

  python3 paper/figures/make_figures.py      # writes fig1–fig4 *.svg next to this file
"""

from __future__ import annotations

import json
import random
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]

# Reference palette (dataviz skill, light mode); slots 1–2 validated together:
# CVD ΔE 24.7, normal-vision ΔE 33.6, both ≥ 3:1 on the surface.
SURFACE, INK, INK2, MUTED = "#fcfcfb", "#0b0b0b", "#52514e", "#898781"
GRID, AXIS = "#e1e0d9", "#c3c2b7"
BLUE, ORANGE = "#2a78d6", "#eb6834"
FONT = 'system-ui, -apple-system, "Segoe UI", Helvetica, Arial, sans-serif'

ARMS = ["A_prompt", "A_know", "A_retry", "B_generic", "C_domain", "C_know"]


class Svg:
    def __init__(self, w: int, h: int, title: str, desc: str):
        self.w, self.h = w, h
        self.parts = [
            f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" width="{w}" height="{h}" '
            f'font-family=\'{FONT}\' role="img" aria-labelledby="t d">',
            f"<title id=\"t\">{esc(title)}</title><desc id=\"d\">{esc(desc)}</desc>",
            f'<rect width="{w}" height="{h}" fill="{SURFACE}"/>',
        ]

    def add(self, s: str) -> None:
        self.parts.append(s)

    def text(self, x, y, s, size=12, fill=INK2, anchor="start", weight=400, tabular=False):
        style = ' style="font-variant-numeric: tabular-nums"' if tabular else ""
        self.add(f'<text x="{x:.1f}" y="{y:.1f}" font-size="{size}" fill="{fill}" '
                 f'text-anchor="{anchor}" font-weight="{weight}"{style}>{esc(s)}</text>')

    def line(self, x1, y1, x2, y2, stroke=GRID, width=1, dash=None):
        d = f' stroke-dasharray="{dash}"' if dash else ""
        self.add(f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" stroke="{stroke}" '
                 f'stroke-width="{width}"{d}/>')

    def dot(self, x, y, fill, r=5, hollow=False):
        if hollow:
            self.add(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{r}" fill="{SURFACE}" stroke="{fill}" stroke-width="2"/>')
        else:  # 2px surface ring so overlapping marks stay legible
            self.add(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{r}" fill="{fill}" stroke="{SURFACE}" stroke-width="2"/>')

    def bar(self, x0, x1, y, h, fill, round_end=True):
        """Horizontal bar segment; the data end (right) gets 4px corners, the baseline end stays square."""
        if x1 - x0 < 0.5:
            return
        r = min(4, (x1 - x0) / 2, h / 2) if round_end else 0
        self.add(f'<path d="M{x0:.1f},{y:.1f} H{x1 - r:.1f} Q{x1:.1f},{y:.1f} {x1:.1f},{y + r:.1f} '
                 f'V{y + h - r:.1f} Q{x1:.1f},{y + h:.1f} {x1 - r:.1f},{y + h:.1f} H{x0:.1f} Z" fill="{fill}"/>')

    def legend(self, x, y, items):
        for label, color, kind in items:
            if kind == "dot":
                self.dot(x + 5, y - 4, color)
            else:
                self.add(f'<rect x="{x}" y="{y - 9}" width="10" height="10" rx="2" fill="{color}"/>')
            self.text(x + 16, y, label, 12, INK2)
            x += 16 + 7.0 * len(label) + 18

    def save(self, name: str) -> Path:
        out = HERE / name
        out.write_text("\n".join(self.parts + ["</svg>"]) + "\n", encoding="utf-8")
        return out


def esc(s: str) -> str:
    return str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


# ── Figure 1: resolve rate per condition, and what the extra calls added ────────────────
def fig1() -> Path:
    # Section 5.1, first table (360 runs, 60 per condition)
    total = {"A_prompt": 60.0, "A_know": 58.3, "A_retry": 63.3, "B_generic": 68.3, "C_domain": 66.7, "C_know": 73.3}
    within = {"A_prompt": 60.0, "A_know": 58.3, "A_retry": 60.0, "B_generic": 63.3, "C_domain": 58.3, "C_know": 68.3}
    past40 = {"A_prompt": 0, "A_know": 0, "A_retry": 11, "B_generic": 12, "C_domain": 19, "C_know": 14}
    W, H, L, R, T, row = 720, 420, 110, 590, 98, 40
    lo, hi = 50.0, 80.0
    sx = lambda v: L + (v - lo) / (hi - lo) * (R - L)
    s = Svg(W, H, "Figure 1. Hidden-test resolve rate by condition",
            "Dumbbell chart: for each of six conditions, the resolve rate within 40 tool calls and with all calls. "
            "C_know reaches 73.3% overall and 68.3% within 40 calls; A_know 58.3% in both.")
    s.text(20, 28, "Resolve rate by condition (360 runs, 60 per condition)", 15, INK, weight=600)
    s.legend(20, 54, [("Within 40 calls", BLUE, "dot"), ("All calls (gated arms may use up to 60)", ORANGE, "dot")])
    bottom = T + row * len(ARMS) - row / 2 + 8
    for v in range(50, 81, 5):
        s.line(sx(v), T - 14, sx(v), bottom, GRID)
        s.text(sx(v), bottom + 18, f"{v}%", 11, MUTED, "middle", tabular=True)
    s.text(R + 18, T - 34, "runs past", 11, MUTED)
    s.text(R + 18, T - 21, "call 40", 11, MUTED)
    for i, arm in enumerate(ARMS):
        y = T + i * row
        primary = arm in ("A_know", "C_know")
        s.text(L - 14, y + 4, arm, 12.5, INK if primary else INK2, "end", 600 if primary else 400)
        if total[arm] != within[arm]:
            s.line(sx(within[arm]), y, sx(total[arm]), y, AXIS, 2)
        s.dot(sx(within[arm]), y, BLUE)
        s.dot(sx(total[arm]), y, ORANGE)
        if primary:  # selective direct labels: the primary contrast only
            s.text(sx(total[arm]) + 10, y + 4, f"{total[arm]:.1f}%", 12, INK, weight=600, tabular=True)
        s.text(R + 18, y + 4, str(past40[arm]), 12, INK2, tabular=True)
    s.text(L, H - 34, "Primary contrast C_know vs A_know: +15.0 pp overall, +10.0 pp within 40 calls (p = 0.074).",
           11.5, INK2)
    s.text(L, H - 16, "Ungated arms cannot pass call 40, so their two dots coincide.", 11.5, MUTED)
    return s.save("fig1-resolve-by-condition.svg")


# ── Figure 2: contrasts with 95% CIs against the pre-registered noise floor ───────────────
def fig2() -> Path:
    # Section 5.1, second table: (label, diff pp, CI or None, task-level p, primary?)
    rows = [
        ("C_know vs A_know (primary)", 15.0, (3.3, 26.7), "0.023", True),
        ("C_know vs A_know, ≤ 40 calls", 10.0, None, "0.074", True),
        ("C_domain vs B_generic", -1.7, (-10.0, 6.7), "0.75", False),
        ("C_domain vs A_retry", 3.3, (-3.3, 10.0), "0.31", False),
        ("B_generic vs A_retry", 5.0, (-3.3, 16.7), "0.38", False),
        ("A_know vs A_prompt", -1.7, (-11.7, 8.3), "0.73", False),
        ("A_retry vs A_prompt", 3.3, (-5.0, 11.7), "0.34", False),
        ("Interaction (two-sided)", 8.3, (-5.0, 21.7), "0.37", False),
    ]
    W, H, L, R, T, row = 720, 420, 200, 600, 84, 36
    lo, hi, floor = -15.0, 30.0, 9.0
    sx = lambda v: L + (v - lo) / (hi - lo) * (R - L)
    s = Svg(W, H, "Figure 2. Contrasts with 95% CIs and the noise floor",
            "Forest plot of eight contrasts in percentage points with task-bootstrap 95% CIs. Only the primary "
            "contrast (C_know vs A_know, +15.0, CI +3.3 to +26.7) clears the 9.0 pp noise floor; its 40-call "
            "version (+10.0) has p = 0.074.")
    s.text(20, 28, "Contrasts: difference in resolve rate (pp), 95% CI by task bootstrap", 15, INK, weight=600)
    s.legend(20, 54, [("Primary contrast", BLUE, "dot"), ("Secondary / post-hoc", INK2, "dot")])
    bottom = T + row * len(rows) - row / 2 + 6
    for v in range(-15, 31, 5):
        s.line(sx(v), T - 16, sx(v), bottom, GRID)
        s.text(sx(v), bottom + 18, f"{v:+d}" if v else "0", 11, MUTED, "middle", tabular=True)
    s.line(sx(0), T - 16, sx(0), bottom, AXIS, 1.5)
    s.line(sx(floor), T - 16, sx(floor), bottom, INK2, 1, dash="4 3")  # a threshold, so dashed
    s.text(sx(floor) + 4, T - 20, "noise floor 9.0 pp", 11, INK2)
    s.text(R + 22, T - 20, "task-level p", 11, MUTED)
    for i, (label, d, ci, p, primary) in enumerate(rows):
        y = T + i * row
        color = BLUE if primary else INK2
        s.text(L - 14, y + 4, label.strip(), 12.5, INK if primary else INK2, "end", 600 if i == 0 else 400)
        if ci:
            s.line(sx(ci[0]), y, sx(ci[1]), y, color, 2)
            s.dot(sx(d), y, color)
        else:
            s.dot(sx(d), y, color, hollow=True)
            s.text(sx(d) + 10, y + 4, "no CI reported", 11, MUTED)
        if i == 0:
            s.text(sx(ci[1]) + 8, y + 4, f"{d:+.1f}", 12, INK, weight=600, tabular=True)
        s.text(R + 22, y + 4, p, 12, INK2, tabular=True)
    s.text(L, H - 18, "Rule: diff > floor and p ≤ 0.05. Interaction = (C_know − A_know) − (C_domain − A_prompt).",
           11.5, INK2)
    return s.save("fig2-contrasts.svg")


# ── Figure 3: FinSWE-21 per arm (18 runs, descriptive) ───────────────────────────────────
def fig3() -> Path:
    kernels = ("v10", "v11", "v12", "v13")
    rows = [json.loads(x) for k in kernels
            for x in (ROOT / f"results/{k}/results.jsonl").read_text().splitlines() if x.strip()]
    n = len(kernels) * 3  # seeds per condition
    early = {a: 0 for a in ARMS}
    late = {a: 0 for a in ARMS}
    for r in rows:
        if r["resolved"]:
            (early if r["tool_calls"] <= 40 else late)[r["condition"]] += 1
    gate = {a: [r for r in rows if r["condition"] == a and r["final_gate_passed"]] for a in ARMS}
    wrong = {a: sum(1 for r in gate[a] if not r["resolved"]) for a in ARMS}
    W, H, L, R, T, row, bh = 760, 384, 110, 420, 82, 38, 16
    sx = lambda v: L + v / n * (R - L)
    s = Svg(W, H, "Figure 3. FinSWE-21 across four kernels: runs resolved per condition",
            f"Stacked bars of resolved runs out of {n} per condition over kernels v10–v13, split by whether the win "
            f"came within 40 calls. C_know {early['C_know']} within and {late['C_know']} after call 40; A_know "
            f"{early['A_know']}; C_domain {early['C_domain'] + late['C_domain']}; B_generic "
            f"{early['B_generic'] + late['B_generic']}, its gate passing {wrong['B_generic']} patches that failed the "
            f"hidden tests.")
    s.text(20, 28, f"FinSWE-21 (public task), kernels v10–v13: runs resolved of {n} per condition", 15, INK, weight=600)
    s.legend(20, 54, [("Resolved within 40 calls", BLUE, "box"), ("Resolved after call 40", ORANGE, "box")])
    bottom = T + row * len(ARMS) - row / 2 + 6
    for v in range(0, n + 1, 3):
        s.line(sx(v), T - 16, sx(v), bottom, GRID if v else AXIS, 1 if v else 1.5)
        s.text(sx(v), bottom + 18, str(v), 11, MUTED, "middle", tabular=True)
    s.text(R + 22, T - 20, "note", 11, MUTED)
    notes = {"A_know": f"ties C_know within 40 calls ({early['A_know']} vs {early['C_know']})",
             "A_retry": "content-free retry rescued none",
             "B_generic": f"gate passed {len(gate['B_generic'])}; {wrong['B_generic']} failed hidden tests",
             "C_domain": f"gate passed {len(gate['C_domain'])}; {wrong['C_domain']} failed hidden tests",
             "C_know": f"{late['C_know']} of {early['C_know'] + late['C_know']} wins after call 40"}
    for i, arm in enumerate(ARMS):
        y = T + i * row
        s.text(L - 14, y + 4, arm, 12.5, INK2, "end")
        e, l = early[arm], late[arm]
        if e:
            s.bar(sx(0), sx(e) - (1 if l else 0), y - bh / 2, bh, BLUE, round_end=not l)
        if l:
            s.bar(sx(e) + (1 if e else 0), sx(e + l), y - bh / 2, bh, ORANGE)
        if not e + l:
            s.text(sx(0) + 6, y + 4, "0", 12, MUTED, tabular=True)
        if arm in notes:
            s.text(R + 22, y + 4, notes[arm], 11.5, INK2)
    s.text(L, H - 34, "One task, 4 kernels × 3 seeds; v12–v13 ran with a changed prompt and hygiene message.",
           11.5, INK2)
    s.text(L, H - 16, "Post hoc and descriptive: not pooled with the 360 core runs.", 11.5, MUTED)
    return s.save("fig3-finswe21.svg")


# ── Figure 4: FinSWE-21 contrasts over the 72 runs (post hoc) ───────────────────────────────
KERNELS = ("v10", "v11", "v12", "v13")


def finswe21_rows() -> list[dict]:
    """The 72 PUB-21 runs, each kernel-seed pair relabelled as its own seed (k·10 + seed)."""
    out = []
    for k, v in enumerate(KERNELS):
        for x in (ROOT / f"results/{v}/results.jsonl").read_text().splitlines():
            if x.strip():
                r = json.loads(x)
                out.append({**r, "seed": k * 10 + r["seed"], "kernel": v})
    return [r for r in out if not r.get("contaminated")]


def fig4() -> Path:
    sys.path.insert(0, str(ROOT / "pilot"))
    import analyze  # noqa: PLC0415  (the pre-registered analysis, stdlib only)

    rows = finswe21_rows()
    within40 = [{**r, "resolved": bool(r["resolved"] and r["tool_calls"] <= 40)} for r in rows]

    def contrast(rs, x, y):
        """Mean paired difference and a 95% CI by bootstrap over the kernel-seed pairs (one task, so
        the task-cluster bootstrap of Section 5.1 would be degenerate)."""
        idx = {(r["seed"], r["condition"]): float(r["resolved"]) for r in rs}
        d = [idx[(sd, x)] - idx[(sd, y)] for sd in sorted({r["seed"] for r in rs})]
        rng = random.Random(0)
        boots = [sum(rng.choice(d) for _ in d) / len(d) for _ in range(4000)]
        lo, hi = analyze._quantiles(boots)
        return 100 * sum(d) / len(d), (100 * lo, 100 * hi), analyze.placebo(rs, x, y)["p"]

    specs = [(rows, "C_know", "A_know", "C_know vs A_know (primary)", True),
             (within40, "C_know", "A_know", "C_know vs A_know, ≤ 40 calls", True)]
    specs += [(rows, x, y, f"{x} vs {y}", False) for x, y, _ in analyze.CONTRASTS if (x, y) != ("C_know", "A_know")]
    res = [(label, *contrast(rs, x, y), primary) for rs, x, y, label, primary in specs]
    sec = [i for i, r in enumerate(res) if not r[4]]
    holm = dict(zip(sec, analyze.holm([res[i][3] for i in sec])))
    floor = 100 * analyze.noise_floor(rows)["floor"]

    W, H, L, R, T, row = 760, 400, 220, 600, 84, 36
    lo, hi = -60.0, 80.0
    sx = lambda v: L + (v - lo) / (hi - lo) * (R - L)
    s = Svg(W, H, "Figure 4. FinSWE-21 contrasts over kernels v10–v13",
            f"Forest plot of seven contrasts on the public task, 72 runs, 95% CIs by bootstrap over 12 kernel-seed "
            f"pairs. C_know vs A_know is {res[0][1]:+.1f} pp, above the {floor:.1f} pp noise floor, but "
            f"{res[1][1]:+.1f} pp within 40 calls.")
    s.text(20, 28, "FinSWE-21, kernels v10–v13: contrasts (pp), 95% CI over 12 kernel-seed pairs", 15, INK, weight=600)
    s.legend(20, 54, [("Primary contrast", BLUE, "dot"), ("Secondary", INK2, "dot")])
    bottom = T + row * len(res) - row / 2 + 6
    for v in range(-60, 81, 20):
        s.line(sx(v), T - 16, sx(v), bottom, GRID)
        s.text(sx(v), bottom + 18, f"{v:+d}" if v else "0", 11, MUTED, "middle", tabular=True)
    s.line(sx(0), T - 16, sx(0), bottom, AXIS, 1.5)
    s.line(sx(floor), T - 16, sx(floor), bottom, INK2, 1, dash="4 3")  # a threshold, so dashed
    s.text(sx(floor) + 4, T - 20, f"noise floor {floor:.1f} pp", 11, INK2)
    s.text(R + 22, T - 20, "placebo p (Holm)", 11, MUTED)
    for i, (label, d, (clo, chi), p, primary) in enumerate(res):
        y = T + i * row
        color = BLUE if primary else INK2
        s.text(L - 14, y + 4, label, 12.5, INK if primary else INK2, "end", 600 if i == 0 else 400)
        s.line(sx(clo), y, sx(chi), y, color, 2)
        s.dot(sx(d), y, color)
        if primary:
            s.text(sx(chi) + 8, y + 4, f"{d:+.1f}", 12, INK, weight=600, tabular=True)
        s.text(R + 22, y + 4, f"{p:.3f}" + (f" ({holm[i]:.3f})" if i in holm else ""), 12, INK2, tabular=True)
    s.text(20, H - 34, "Post hoc, one task; v12–v13 ran with a changed prompt and hygiene message. Not pooled with Figure 2.",
           11.5, INK2)
    s.text(20, H - 16, "Secondary p in parentheses is Holm-adjusted over the five secondary contrasts.", 11.5, MUTED)
    return s.save("fig4-finswe21-contrasts.svg")


if __name__ == "__main__":
    for f in (fig1, fig2, fig3, fig4):
        print(f().relative_to(ROOT))
