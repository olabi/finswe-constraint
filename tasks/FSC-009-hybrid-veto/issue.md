# Hybrid mode: a low-confidence AI objection permanently blocks rule trades

**Observed.** In `--mode hybrid` (the rule leads and the AI may veto), my conservative
local model answers HOLD with low confidence on almost every rule BUY. An example from
the decision log: rule BUY (pullback re-entry), AI `HOLD @ 0.32` ("MACD negative,
weak"). Every disagreement counts as a veto, so the bot never trades.

**Expected.**
- Add `EngineSettings.ai_veto_confidence` (default `0.6`).
- In hybrid mode, if the AI disagrees with the rule *and* its confidence is at least
  `ai_veto_confidence`, the veto stands (final = HOLD, not executed).
- If the AI disagrees with confidence below the threshold, treat it as a weak
  objection and execute the rule's action.
- Agreement and protective exits (stop-loss / take-profit, which skip AI review) keep
  their current behavior.
