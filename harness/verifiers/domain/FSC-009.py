"""Hybrid mode: AI veto requires confidence >= ai_veto_confidence (default 0.6)."""
import sys; sys.path.insert(0, sys.argv[1])
from kit import Check, ScriptedAdvisor, Violation, engine, last_decision, qty, run_checks
from ai_trader.strategy import SmaRsiStrategy

# 28 bars of decline then a 6-bar rebound: SMA5 crosses above SMA20 on the last bar
# with RSI < 70 (searched; the hidden tests use a different 30+5 path).
_DEC = [210.0 - 1.5 * i for i in range(28)]
CROSS = _DEC + [_DEC[-1] - 1.5 + 3.5 * (j + 1) for j in range(6)]


def run(conf, action="HOLD"):
    adv = ScriptedAdvisor(action, conf, "lagging indicators still weak")
    eng, paper, tmp = engine(CROSS, symbols=["035720"], mode="hybrid", advisor=adv,
                             strategy=SmaRsiStrategy())
    eng.run(max_polls=1)
    rec = last_decision(tmp, "035720")
    rule = rec.get("rule")
    if (rule.get("action") if isinstance(rule, dict) else rule) != "BUY":
        raise RuntimeError(f"scenario invalid: rule={rec.get('rule')} (expected BUY)")
    return rec, qty(paper, "035720")


def weak_objection_executes():
    rec, q = run(0.55)
    if not (rec.get("final") == "BUY" and q > 0):
        raise Violation(f"AI HOLD@0.55 blocked the rule BUY (final={rec.get('final')}, "
                        f"executed={rec.get('executed')})")


def confident_objection_vetoes():
    rec, q = run(0.75)
    if rec.get("final") != "HOLD" or q > 0:
        raise Violation(f"AI HOLD@0.75 did not veto (final={rec.get('final')}, shares={q:g})")


def threshold_is_inclusive():
    rec, q = run(0.60)
    if rec.get("final") != "HOLD" or q > 0:
        raise Violation(f"AI HOLD@0.60 (== threshold) did not veto (final={rec.get('final')})")


def agreement_executes():
    rec, q = run(0.7, action="BUY")
    if not (rec.get("final") == "BUY" and q > 0):
        raise Violation(f"AI agreed but BUY not executed (final={rec.get('final')})")


run_checks([
    Check("D-VETO-1", "weak AI objection does not block a rule BUY",
          "hybrid, 035720 SMA5/20 golden cross (rule BUY), AI HOLD@0.55",
          "final BUY, shares bought", weak_objection_executes),
    Check("D-VETO-2", "confident AI objection vetoes",
          "hybrid, same cross, AI HOLD@0.75", "final HOLD, nothing bought", confident_objection_vetoes),
    Check("D-VETO-3", "veto threshold is inclusive (>= 0.6)",
          "hybrid, same cross, AI HOLD@0.60", "final HOLD, nothing bought", threshold_is_inclusive),
    Check("D-VETO-4", "agreement still executes",
          "hybrid, same cross, AI BUY@0.70", "final BUY, shares bought", agreement_executes),
])
