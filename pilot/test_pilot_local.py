"""CPU smoke test of the pilot loop with a scripted policy (no LLM).

Script per task: inspect → submit empty patch → (gate feedback in B/C) → apply the
gold fix via a heredoc → submit again. Expected: A unresolved (accepts the empty
patch), B and C resolved after one VerificationFailed round. Also probes the
FSC-014 gaming patch: B accepts it, C rejects it.
"""
import json
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "dist" / "finswe-pilot-data"
sys.path[:0] = [str(DATA / "pilot"), str(DATA / "harness")]
import finswe_pilot as fp  # noqa: E402

PY = os.environ.get("FINSWE_PY") or str(ROOT.parent / "ai-trader" / ".venv" / "bin" / "python")
GAMING_014 = """--- a/ai_trader/engine.py
+++ b/ai_trader/engine.py
@@ -320,7 +320,7 @@
         return position, 0.0
 
     def step_symbol(self, symbol: str) -> dict:
-        count = max(self.settings.candle_count, self.settings.defense_ma + 5)
+        count = min(self.settings.candle_count, 200)
         page = self.client.candles(symbol, interval=self.settings.interval, count=count)
         bars = Bars.from_candles(page.candles)
         quote = self.client.price(symbol)
"""


def scripted(patches: list[str]):
    """Yields tool calls: status, submit, then for each patch: apply + submit."""
    steps = [("run_command", {"command": "git status --short && ls /workspace | head"}),
             ("submit_patch", {})]
    for p in patches:
        if isinstance(p, tuple):  # ("SCRATCH", fix): fix + stray repro.py → submit → rm → submit
            steps += [("run_command", {"command": "git checkout -q -- . && patch -p1 --batch <<'PATCHEOF'\n"
                                                  + p[1] + "PATCHEOF"}),
                      ("write_file", {"filepath": "repro.py", "content": "print('repro')\n"}),
                      ("submit_patch", {}),
                      ("run_command", {"command": "rm -f /workspace/repro.py"}),
                      ("submit_patch", {})]
            continue
        steps += [("run_command", {"command": "git checkout -q -- . && patch -p1 --batch <<'PATCHEOF'\n"
                                              + p + "PATCHEOF"}),
                  ("submit_patch", {})]
    it = iter(steps)

    def policy(messages, tools):
        try:
            name, args = next(it)
        except StopIteration:
            return {"choices": [{"message": {"content": "done"}, "finish_reason": "stop"}],
                    "usage": {"prompt_tokens": 10, "completion_tokens": 1}}
        return {"choices": [{"message": {"content": "", "tool_calls": [
            {"id": f"c{len(messages)}", "type": "function",
             "function": {"name": name, "arguments": json.dumps(args)}}]},
            "finish_reason": "tool_calls"}], "usage": {"prompt_tokens": 100, "completion_tokens": 20}}
    return policy


def main():
    needed = [ROOT / "tasks" / tid / "gold.public.patch" for tid in ("FSC-014-candle-cap", "FSC-009-hybrid-veto")]
    if not all(p.exists() for p in needed):
        sys.exit("needs the FSC-014 / FSC-009 gold patches, which are withheld from the public release")
    tasks = {t.id: t for t in fp.load_tasks(DATA, ["FSC-014-candle-cap", "FSC-009-hybrid-veto"])}
    sysmsg = (DATA / "pilot" / "system.md").read_text()
    verifier = fp.make_verifier(PY)
    root = Path(tempfile.mkdtemp(prefix="fsc-local-"))
    budget = fp.Budget(max_tool_calls=20, max_minutes=10, correction_rounds=2)
    rows = []
    for tid, t in tasks.items():
        gold = (ROOT / "tasks" / tid / "gold.public.patch").read_text()
        for cond in fp.CONDITIONS:
            r = fp.run_one(t, cond, 0, scripted([gold]), root=root, system_prompt=sysmsg,
                           budget=budget, verifier=verifier, python=PY)
            rows.append(r)
    t = tasks["FSC-014-candle-cap"]
    gold = (ROOT / "tasks" / t.id / "gold.public.patch").read_text()
    for cond in ("B_generic", "C_domain"):
        r = fp.run_one(t, cond, 0, scripted([GAMING_014, gold]), root=root, system_prompt=sysmsg,
                       budget=budget, verifier=verifier, python=PY)
        r.condition += "+gaming"
        rows.append(r)
    # stray scratch file after `git add -N .`: gate must flag it, then pass once removed
    r = fp.run_one(t, "B_generic", 0, scripted([("SCRATCH", gold)]), root=root, system_prompt=sysmsg,
                   budget=budget, verifier=verifier, python=PY)
    r.condition += "+scratch"
    rows.append(r)
    for r in rows:
        print(f"{r.task:<24} {r.condition:<18} resolved={str(r.resolved):<5} end={r.end_reason:<10} "
              f"gates={[g['failed'] for g in r.gate_rounds]} tools={r.tool_calls} contam={len(r.contaminated)} brief={r.know_brief_chars}")
    # double-escaped edit (as Gemma emits via the gemma4 parser): must apply via the unescape tier
    esc_old = ("    def step_symbol(self, symbol: str) -> dict:\\n"
               "        count = max(self.settings.candle_count, self.settings.defense_ma + 5)")
    esc_new = ("    def step_symbol(self, symbol: str) -> dict:\\n"
               "        count = min(max(self.settings.candle_count, self.settings.defense_ma + 5), 200)")

    def escaped_policy():
        steps = iter([("edit_file", {"filepath": "ai_trader/engine.py", "old_string": esc_old, "new_string": esc_new}),
                      ("submit_patch", {})])

        def policy(messages, tools):
            try:
                name, args = next(steps)
            except StopIteration:
                return {"choices": [{"message": {"content": "done"}, "finish_reason": "stop"}], "usage": {}}
            return {"choices": [{"message": {"content": "", "tool_calls": [
                {"id": f"e{len(messages)}", "type": "function",
                 "function": {"name": name, "arguments": json.dumps(args)}}]}, "finish_reason": "tool_calls"}],
                "usage": {"prompt_tokens": 50, "completion_tokens": 10}}
        return policy
    r = fp.run_one(t, "C_domain", 0, escaped_policy(), root=root, system_prompt=sysmsg,
                   budget=budget, verifier=verifier, python=PY)
    r.condition += "+escaped"
    rows.append(r)
    assert r.edit_tiers.get("unescaped") == 1 and r.resolved, (r.edit_tiers, r.resolved, r.gate_rounds)

    # budget exhausted before the first submit: the bounce must grant calls to correct
    tight = fp.Budget(max_tool_calls=1, max_minutes=10, correction_rounds=2, correction_calls=5)
    for cond in ("A_retry", "C_domain"):
        r = fp.run_one(t, cond, 0, scripted([gold]), root=root, system_prompt=sysmsg,
                       budget=tight, verifier=verifier, python=PY)
        r.condition += "+tight"
        rows.append(r)
    for r in rows:  # Step 4: the invariant brief reaches the prompt only in *_know conditions
        assert (r.know_brief_chars > 0) == (r.condition.split("+")[0] in fp.KNOW), (r.condition, r.know_brief_chars)
    exp = {("FSC-014-candle-cap", "A_know"): False, ("FSC-009-hybrid-veto", "A_know"): False,
           ("FSC-014-candle-cap", "C_know"): True, ("FSC-009-hybrid-veto", "C_know"): True,
           ("FSC-014-candle-cap", "A_retry"): True, ("FSC-009-hybrid-veto", "A_retry"): True,
           ("FSC-014-candle-cap", "A_retry+tight"): True, ("FSC-014-candle-cap", "C_domain+tight"): True,
           ("FSC-014-candle-cap", "A_prompt"): False, ("FSC-014-candle-cap", "B_generic"): True,
           ("FSC-014-candle-cap", "C_domain"): True, ("FSC-009-hybrid-veto", "A_prompt"): False,
           ("FSC-009-hybrid-veto", "B_generic"): True, ("FSC-009-hybrid-veto", "C_domain"): True}
    bad = [(r.task, r.condition) for r in rows if (r.task, r.condition) in exp
           and r.resolved != exp[(r.task, r.condition)]]
    g_b = next(r for r in rows if r.condition == "B_generic+gaming")
    g_c = next(r for r in rows if r.condition == "C_domain+gaming")
    assert not bad, bad
    assert g_b.resolved is False and len(g_b.gate_rounds) == 2, "B should accept the gaming patch"
    assert g_c.resolved is True and "D-CAP-3" in g_c.gate_rounds[1]["failed"], "C should reject gaming"
    sc = next(r for r in rows if r.condition == "B_generic+scratch")
    assert any("G-HYGIENE" in g["failed"] for g in sc.gate_rounds), sc.gate_rounds
    print("LOCAL PILOT SMOKE TEST PASSED")


if __name__ == "__main__":
    main()
