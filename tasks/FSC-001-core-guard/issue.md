# AI-only SELL liquidated a protected core holding in `--mode ai`

**Observed (live account).** I run the engine in `--mode ai` and list my long-term
holding in `--accumulate` so the bot treats it as a core position (buy and hold, never
trend-sold). The rule engine said **HOLD** for that symbol, but the advisor returned
`SELL` with confidence 0.85 ("below regime line, MACD negative"), and the engine
executed it — the whole core position was sold.

**Expected.**
- For a symbol in `settings.accumulate`, an AI decision alone must never close the
  position. The trade should be recorded as not executed, with final action `HOLD`.
- If the *rule itself* emits a protective SELL for that symbol (e.g. its
  capital-preservation floor), the sell must still go through.
- Symbols that are **not** in `accumulate` keep today's `--mode ai` behavior: an AI
  SELL is executed as before.
