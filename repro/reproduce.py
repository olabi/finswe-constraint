"""One command that recomputes every table in paper/writeup.md (Sections 5.1, 5.2 and 5.4).

  python3 repro/reproduce.py

1. Verifies results/SHA256SUMS: every run record is the file the paper used.
2. Recomputes the core experiment (360 runs, results/core/v5, v6, v8) and FinSWE-21 (72 runs,
   results/v10–v13): rates, the 40-call budget analysis, every contrast with its CI and p-values,
   the interaction, the seed-2 counterfactual, and the per-kernel FinSWE-21 tables.
3. Compares each number with repro/expected.json, which holds what the paper prints, at the
   printed precision, and prints a markdown report.
4. Redraws the figures (paper/figures/make_figures.py).

Exit status 0 only if every checksum and every number matches. Stdlib only.

Analyses that are not in pilot/analyze.py (the post-hoc ones of Section 4) are defined here:
  task-level exact p   sign-flip permutation over task-level differences (each the mean over its
                       seeds), enumerated exactly; one-sided unless marked
  interaction          (C_know − A_know) − (C_domain − A_prompt) per (task, seed); task-bootstrap CI
                       as in analyze.paired; two-sided exact sign-flip p over task means
  within 40 calls      a run counts as resolved only if it resolved using ≤ 40 tool calls
"""

from __future__ import annotations

import hashlib
import json
import random
import runpy
import sys
from collections import Counter, defaultdict
from fractions import Fraction
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "pilot"))
import analyze  # noqa: E402  (the pre-registered analysis)

ARMS = ["A_prompt", "A_know", "A_retry", "B_generic", "C_domain", "C_know"]
GATED = ["A_retry", "B_generic", "C_domain", "C_know"]
CORE_KERNELS = ("v5", "v6", "v8")             # seeds 0, 1, 2 (pilot-log.md)
FINSWE21_KERNELS = ("v10", "v11", "v12", "v13")


# ── checksums ──────────────────────────────────────────────────────────────────────────────
def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def verify_checksums() -> list[str]:
    sums = ROOT / "results" / "SHA256SUMS"
    if not sums.exists():
        return ["results/SHA256SUMS is missing"]
    bad = []
    for line in sums.read_text().splitlines():
        if not line.strip():
            continue
        digest, rel = line.split(maxsplit=1)
        path = ROOT / rel.lstrip("*")
        if not path.exists():
            bad.append(f"missing: {rel}")
        elif sha256(path) != digest:
            bad.append(f"checksum mismatch: {rel}")
    return bad


# ── loading ────────────────────────────────────────────────────────────────────────────────
def load(kernels, relabel: bool) -> list[dict]:
    """Run records of the given kernels; with relabel, seed becomes kernel_index·10 + seed so that
    kernels sharing seed numbers stay distinct (FinSWE-21)."""
    rows = []
    for k, v in enumerate(kernels):
        for line in (ROOT / "results" / ("core" if not relabel else "") / v / "results.jsonl").read_text().splitlines():
            if line.strip():
                r = json.loads(line)
                rows.append({**r, "kernel": v, "seed": k * 10 + r["seed"] if relabel else r["seed"]})
    return rows


def within_40(rows: list[dict]) -> list[dict]:
    return [{**r, "resolved": bool(r["resolved"] and r["tool_calls"] <= 40)} for r in rows]


# ── analyses not in analyze.py ─────────────────────────────────────────────────────────────
def task_means(rows, fn) -> dict[str, Fraction]:
    """Per task, the mean over seeds of fn(values by condition) for seeds that have every arm fn needs."""
    by = defaultdict(dict)
    for r in rows:
        by[(r["task"], r["seed"])][r["condition"]] = Fraction(int(bool(r["resolved"])))
    acc = defaultdict(list)
    for (task, _), conds in by.items():
        v = fn(conds)
        if v is not None:
            acc[task].append(v)
    return {t: sum(v) / len(v) for t, v in acc.items()}


def exact_signflip(values: list[Fraction], two_sided: bool = False) -> float:
    """Exact sign-flip permutation p for the sum of `values` (one-sided: P(sum ≥ observed))."""
    obs = sum(values)
    dist = Counter({Fraction(0): 1})
    for v in values:
        if v == 0:
            continue
        nxt = Counter()
        for s, c in dist.items():
            nxt[s + v] += c
            nxt[s - v] += c
        dist = nxt
    total = sum(dist.values())
    hit = sum(c for s, c in dist.items() if (abs(s) >= abs(obs) if two_sided else s >= obs))
    return hit / total


def pair(x, y):
    return lambda c: (c[x] - c[y]) if x in c and y in c else None


def interaction(c):
    need = ("C_know", "A_know", "C_domain", "A_prompt")
    return (c["C_know"] - c["A_know"]) - (c["C_domain"] - c["A_prompt"]) if all(k in c for k in need) else None


def interaction_ci(rows, seed=0, b=4000) -> tuple[float, float, float]:
    by = defaultdict(dict)
    for r in rows:
        by[(r["task"], r["seed"])][r["condition"]] = float(bool(r["resolved"]))
    per_task = defaultdict(list)
    for (task, _), c in by.items():
        v = interaction({k: Fraction(int(x)) for k, x in c.items()})
        if v is not None:
            per_task[task].append(float(v))
    flat = [v for vs in per_task.values() for v in vs]
    rng = random.Random(seed)
    tasks = list(per_task)
    boots = []
    for _ in range(b):
        pick = [v for t in (rng.choice(tasks) for _ in tasks) for v in per_task[t]]
        boots.append(sum(pick) / len(pick))
    lo, hi = analyze._quantiles(boots)
    return sum(flat) / len(flat), lo, hi


def counts(rows):
    out = {}
    for a in ARMS:
        rs = [r for r in rows if r["condition"] == a]
        out[a] = {"n": len(rs), "resolved": sum(bool(r["resolved"]) for r in rs),
                  "within_40": sum(bool(r["resolved"]) and r["tool_calls"] <= 40 for r in rs),
                  "past_40": sum(r["tool_calls"] > 40 for r in rs),
                  "resolved_after_40": sum(bool(r["resolved"]) and r["tool_calls"] > 40 for r in rs),
                  "rescued": sum(r.get("resolved_at_first_submit") is False and bool(r["resolved"]) for r in rs),
                  "harmed": sum(r.get("resolved_at_first_submit") is True and not r["resolved"] for r in rs),
                  "first_resolved": sum(r.get("resolved_at_first_submit") is True for r in rs),
                  "gate_passed": sum(bool(r.get("final_gate_passed")) for r in rs),
                  "gate_passed_hidden_failed": sum(bool(r.get("final_gate_passed")) and not r["resolved"]
                                                   for r in rs)}
    return out


# ── the two experiments ────────────────────────────────────────────────────────────────────
def core_numbers(rows: list[dict]) -> dict:
    valid = [r for r in rows if not r.get("contaminated")]
    c = counts(valid)
    nf = analyze.noise_floor(valid)
    out = {"runs": len(rows), "contaminated": len(rows) - len(valid),
           "rate": {a: 100 * c[a]["resolved"] / c[a]["n"] for a in ARMS},
           "rate_within_40": {a: 100 * c[a]["within_40"] / c[a]["n"] for a in ARMS},
           "runs_past_40": {a: c[a]["past_40"] for a in ARMS},
           "resolved_after_40": {a: c[a]["resolved_after_40"] for a in GATED},
           "noise_floor_pp": 100 * nf["floor"], "pooled_seed_sd_pct": 100 * nf["sd_pooled"], "contrasts": {}}
    for x, y, _ in analyze.CONTRASTS:
        pr = analyze.paired(valid, x, y)
        tm = task_means(valid, pair(x, y))
        entry = {"diff": 100 * pr["diff"], "ci": [100 * pr["ci"][0], 100 * pr["ci"][1]],
                 "prereg_p": analyze.placebo(valid, x, y)["p"], "task_p": exact_signflip(list(tm.values()))}
        if (x, y) == analyze.PRIMARY:
            entry["tasks_plus"] = sum(v > 0 for v in tm.values())
            entry["tasks_minus"] = sum(v < 0 for v in tm.values())
        out["contrasts"][f"{x} vs {y}"] = entry
    w = within_40(valid)
    tm = task_means(w, pair("C_know", "A_know"))
    out["primary_within_40"] = {"diff": 100 * analyze.paired(w, "C_know", "A_know")["diff"],
                                "task_p": exact_signflip(list(tm.values())),
                                "tasks_plus": sum(v > 0 for v in tm.values()),
                                "tasks_minus": sum(v < 0 for v in tm.values())}
    d, lo, hi = interaction_ci(valid)
    out["interaction"] = {"diff": 100 * d, "ci": [100 * lo, 100 * hi],
                          "task_p_two_sided": exact_signflip(list(task_means(valid, interaction).values()), True)}
    idx = {(r["task"], r["seed"], r["condition"]): r for r in valid}
    x_only = [(t, s) for (t, s, cnd), r in idx.items() if cnd == "C_know" and r["resolved"]
              and (t, s, "A_know") in idx and not idx[(t, s, "A_know")]["resolved"]]
    y_only = [(t, s) for (t, s, cnd), r in idx.items() if cnd == "A_know" and r["resolved"]
              and (t, s, "C_know") in idx and not idx[(t, s, "C_know")]["resolved"]]
    out["primary_discordant"] = {"x_only": len(x_only), "y_only": len(y_only),
                                 "x_only_seeds_0_1": sum(s < 2 for _, s in x_only), "x_only_seed_2": sum(s == 2 for _, s in x_only),
                                 "y_only_seeds_0_1": sum(s < 2 for _, s in y_only), "y_only_seed_2": sum(s == 2 for _, s in y_only)}
    out["primary_x_only_past_40"] = sum(idx[(t, s, "C_know")]["tool_calls"] > 40 for t, s in x_only)
    s2 = counts([r for r in valid if r["seed"] == 2])
    out["seed2_counterfactual"] = {a: {"rescued": s2[a]["rescued"], "harmed": s2[a]["harmed"]} for a in GATED}
    out["seed2_first_submit_resolved"] = {"C_know": s2["C_know"]["first_resolved"],
                                          "A_know_final": s2["A_know"]["resolved"]}
    return out


def finswe21_numbers(rows: list[dict]) -> dict:
    valid = [r for r in rows if not r.get("contaminated")]
    c = counts(valid)
    w = within_40(valid)
    holm = analyze.holm([analyze.placebo(valid, x, y)["p"] for x, y, _ in analyze.CONTRASTS[1:]])
    cd_bg = [x[:2] for x in analyze.CONTRASTS].index(("C_domain", "B_generic")) - 1
    return {"runs": len(rows), "contaminated": len(rows) - len(valid),
            "resolved": {k: {a: sum(bool(r["resolved"]) for r in valid if r["kernel"] == k and r["condition"] == a)
                             for a in ARMS} for k in FINSWE21_KERNELS},
            "within_40": {a: c[a]["within_40"] for a in ARMS},
            "rescued": {a: c[a]["rescued"] for a in GATED},
            "harmed": {a: c[a]["harmed"] for a in GATED},
            "gate_passed": {a: c[a]["gate_passed"] for a in ("B_generic", "C_domain", "C_know")},
            "gate_passed_hidden_failed": {a: c[a]["gate_passed_hidden_failed"] for a in ("B_generic", "C_domain", "C_know")},
            "noise_floor_pp": 100 * analyze.noise_floor(valid)["floor"],
            "primary": {"diff": 100 * analyze.paired(valid, "C_know", "A_know")["diff"],
                        "placebo_p": analyze.placebo(valid, "C_know", "A_know")["p"],
                        "x_only": analyze.paired(valid, "C_know", "A_know")["x_only"],
                        "y_only": analyze.paired(valid, "C_know", "A_know")["y_only"]},
            "primary_within_40": {"diff": 100 * analyze.paired(w, "C_know", "A_know")["diff"],
                                  "placebo_p": analyze.placebo(w, "C_know", "A_know")["p"]},
            "c_domain_vs_b_generic": {"diff": 100 * analyze.paired(valid, "C_domain", "B_generic")["diff"],
                                      "placebo_p": analyze.placebo(valid, "C_domain", "B_generic")["p"],
                                      "holm_p": holm[cd_bg]}}


# ── comparison with the paper ──────────────────────────────────────────────────────────────
def decimals(x) -> int:
    s = repr(x)
    return len(s.split(".")[1]) if "." in s else 0


def compare(expected, actual, path="") -> list[tuple[str, object, object, bool]]:
    rows = []
    if isinstance(expected, dict):
        for k, v in expected.items():
            if k.startswith("_"):
                continue
            rows += compare(v, (actual or {}).get(k) if isinstance(actual, dict) else None, f"{path}.{k}".lstrip("."))
    elif isinstance(expected, list):
        for i, v in enumerate(expected):
            rows += compare(v, actual[i] if isinstance(actual, list) and i < len(actual) else None, f"{path}[{i}]")
    else:
        if actual is None:
            ok, shown = False, None
        else:
            # Matches if the paper's figure is a correct rounding of the recomputed value (a value on
            # the half step, e.g. 5.65, may be printed either way).
            nd = decimals(expected)
            shown = round(float(actual), max(nd, 3)) if nd else round(float(actual), 3)
            shown = int(shown) if float(shown).is_integer() and not nd else shown
            ok = abs(float(actual) - float(expected)) <= 0.5 * 10 ** -nd + 1e-9
        rows.append((path, expected, shown, ok))
    return rows


def main() -> int:
    expected = json.loads((ROOT / "repro" / "expected.json").read_text())
    report, failures = ["# reproduce.py report", ""], 0

    bad = verify_checksums()
    report.append("## Checksums")
    report += [f"- ✗ {b}" for b in bad] or ["- ✓ every file in results/SHA256SUMS matches"]
    failures += len(bad)

    actual = {}
    if all((ROOT / "results" / "core" / k / "results.jsonl").exists() for k in CORE_KERNELS):
        actual["core"] = core_numbers(load(CORE_KERNELS, relabel=False))
    actual["finswe21"] = finswe21_numbers(load(FINSWE21_KERNELS, relabel=True))

    for part, title in (("core", "Core experiment (Sections 5.1–5.2)"), ("finswe21", "FinSWE-21 (Section 5.4)")):
        report += ["", f"## {title}", "", "| quantity | paper | recomputed | |", "|---|---|---|---|"]
        if part not in actual:
            report.append("| results/core/v5, v6, v8 | – | missing | ✗ |")
            failures += 1
            continue
        for path, exp, got, ok in compare(expected[part], actual[part]):
            report.append(f"| {path} | {exp} | {got} | {'✓' if ok else '✗'} |")
            failures += not ok

    runpy.run_path(str(ROOT / "paper" / "figures" / "make_figures.py"), run_name="__main__")
    report += ["", "## Figures", "- redrawn: paper/figures/fig1–fig4 (.svg)", "",
               f"**{'ALL MATCH' if not failures else f'{failures} MISMATCH(ES)'}**"]
    (ROOT / "repro" / "report.md").write_text("\n".join(report) + "\n")
    print("\n".join(report))
    return 0 if not failures else 1


if __name__ == "__main__":
    sys.exit(main())
