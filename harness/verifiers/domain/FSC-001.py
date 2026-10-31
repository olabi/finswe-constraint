"""Core holdings: an AI-only SELL must never liquidate a symbol in settings.accumulate."""
import sys; sys.path.insert(0, sys.argv[1])  # verifiers/ dir
from kit import Check, ScriptedAdvisor, Violation, engine, last_decision, qty, run_checks

UP = [50.0 + i * 0.12 for i in range(90)]           # calm uptrend, rule has no exit
CRASH = [100.0] * 80 + [58.0]                         # −42% vs cost: capital floor breached


def core_ai_sell():
    eng, paper, tmp = engine(UP, symbols=["000660"], mode="ai",
                             advisor=ScriptedAdvisor("SELL", 0.95, "momentum fading"),
                             holdings={"000660": (3, 55.0)})
    eng.settings.accumulate = frozenset({"000660"})
    eng.run(max_polls=1)
    rec = last_decision(tmp, "000660")
    if qty(paper, "000660") != 3:
        raise Violation(f"position went 3 → {qty(paper, '000660'):g} shares "
                        f"(rule={rec.get('rule')}, ai={rec.get('ai')}, final={rec.get('final')})")
    if rec.get("executed"):
        raise Violation(f"decision logged executed=True with final={rec.get('final')}")


def noncore_ai_sell_still_executes():
    eng, paper, tmp = engine(UP, symbols=["035720"], mode="ai",
                             advisor=ScriptedAdvisor("SELL", 0.9, "valuation"),
                             holdings={"035720": (4, 55.0)})
    eng.settings.accumulate = frozenset({"000660"})  # a different symbol is core
    eng.run(max_polls=1)
    if qty(paper, "035720") != 0:
        rec = last_decision(tmp, "035720")
        raise Violation(f"non-core AI SELL was blocked (final={rec.get('final')}, "
                        f"note={str(rec.get('note'))[:120]!r})")


def core_rule_floor_sell_passes():
    eng, paper, tmp = engine(CRASH, symbols=["000660"], mode="ai",
                             advisor=ScriptedAdvisor("SELL", 0.8, "breakdown"),
                             holdings={"000660": (2, 100.0)})
    eng.settings.accumulate = frozenset({"000660"})
    eng.run(max_polls=1)
    if qty(paper, "000660") != 0:
        rec = last_decision(tmp, "000660")
        raise Violation(f"rule={rec.get('rule')} protective exit was blocked "
                        f"(final={rec.get('final')}, note={str(rec.get('note'))[:120]!r})")


run_checks([
    Check("D-CORE-1", "AI-only SELL must not liquidate a core holding",
          "mode=ai, 000660 in accumulate, calm uptrend (rule HOLD), AI SELL@0.95, 3 shares",
          "position stays 3 shares; decision executed=False", core_ai_sell),
    Check("D-CORE-2", "non-core symbols keep AI SELL authority",
          "mode=ai, 035720 not in accumulate, AI SELL@0.90, 4 shares",
          "position closed", noncore_ai_sell_still_executes),
    Check("D-CORE-3", "rule-originated protective exit on a core holding still executes",
          "mode=ai, 000660 in accumulate, close −42% vs cost (capital floor), AI SELL@0.80",
          "position closed", core_rule_floor_sell_passes),
])
