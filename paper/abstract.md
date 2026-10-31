# Abstract — draft v1 (2026-10-02)

> v0 → v1: (a) incident examples now name what actually happened (session validity /
> stale prices, not look-ahead); (b) look-ahead and future-news leakage are covered
> by *injected* tasks with explicit provenance labels. Bracketed values are
> placeholders to be filled by experiments — do not cite them.

**Knowing Is Not Enforcing: Executable Domain Constraints for Reliable Gemma 4 Developer Agents**

Coding agents built on capable open models often already "know" software-engineering
best practices, yet routinely violate them, because natural-language instructions
are soft constraints. We study whether converting such knowledge into *executable*
constraints makes a fixed, locally deployable model — Gemma 4 31B (QAT W4A16) — a
more reliable developer agent. We introduce **FinSWE-Constraint**, a benchmark of [N]
repository-level tasks in quantitative trading software, each labeled by provenance.
[K] tasks are reconstructed from real incidents in a live-trading system, where code
compiled and passed its unit tests yet violated a domain invariant: an AI override
liquidated a protected core holding, a covered-call ETF was sold by a trend rule, and
the engine acted on stale prices from sessions in which the stock could not trade.
[M] further tasks inject classic quantitative failures that the live system never
hit — look-ahead bias, future-news leakage, and omitted transaction costs — and [C]
control tasks contain no domain invariant at all. Each task pairs an issue with two
disjoint sets of checks: *feedback constraints* exposed to the agent and *held-out
property tests* used only for scoring. Holding model and budget fixed, we compare
prompt-only best practices, an LLM reviewer, generic executable feedback, and domain
executable feedback. Domain constraints change the held-out resolve rate from [A]% to
[B]% relative to prompt-only, catch [C']% of the violations that generic tests miss,
and the agent repairs [D]% of surfaced failures, at [E]× the LLM calls per solved
task; on control tasks they [should not / do not] help. We release tasks, verifiers,
environments, and run records.

## Claims that must be backed before submission
- [K] incident tasks: currently **15 confirmed** (+2 pending confirmation, see
  `task-candidates.md`); 7 extracted and validated so far.
- "compiled and passed its unit tests": true by construction — every FAIL_TO_PASS
  test is new in the fix commit; the pre-fix suite passed at base.
- Results sentence: hypotheses only. If domain feedback ≤ generic feedback, flip the
  framing rather than the data.
