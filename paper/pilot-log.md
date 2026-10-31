# Pilot log

## v1 — 2026-10-02 (FSC-001 × A/B/C, L4×4, Gemma 4 31B QAT W4A16, vLLM 0.19.1)
Pipeline check. Infra worked: wheelhouse install, `adk_submission.VllmServer`,
gemma4 tool parsing, gate, and scoring. **Void:**
`test_advisor.py::test_make_advisor_factory` needs `anthropic`, which the offline
image lacks, so P2P could never pass and B/C's G-REGRESSION was unsatisfiable. The
hygiene check also missed stray files after `git add -N .`.
Anecdote (n=1, re-scored in a correct env): C resolved FSC-001 after two D-CORE-1
feedbacks; A and B did not.

Fixes: G-REGRESSION is relative to base failures in the same environment, scoring
drops P2P tests that fail at base in the environment (and records them), and
hygiene classifies new files by existence at base.

## v2 — 2026-10-02 (7 tasks × A/B/C, 21 runs; queued 6.5 h for L4, ran 75 min)
| | A_prompt | B_generic | C_domain |
|---|---|---|---|
| resolved | 1/7 (FSC-014) | 1/7 (FSC-014) | 1/7 (FSC-014) |

**Not a test of the hypothesis — design flaw:** agents spend almost the whole
40-call budget before the first submit (first gate at call 34–39), so gate feedback
arrived with 0–2 calls left and could not be acted on. Most B/C runs show the same
failure in every round.

Observations worth keeping:
- **Knowing ≠ enforcing, observed:** the system prompt says *scratch files go to /tmp
  only*, yet in 6/7 tasks the agent left `repro.py` in /workspace. G-HYGIENE caught
  it every time. In A, nothing catches it.
- FSC-009 A: the accepted patch broke every test (P2P 0/143). There is no gate in A,
  so it shipped (the Black Cat failure mode). FSC-003 B/C: the final patch had a
  syntax error; the gate caught it, but no budget was left to fix it.
- **Verifier under-specification:** FSC-009 C passed the domain gate yet failed the
  hidden test. The agent passed the AI's low confidence (0.32) to the risk gate on
  the weak-objection path, so the BUY was blocked by `min_confidence`. The verifier
  kit used `min_confidence=0.5` (repo default 0.65), so its 0.55 probe cleared the
  gate. Fixed (kit uses 0.65); the v2 patch is now caught by D-VETO-1. Report the
  verifier-pass/hidden-fail rate as its own metric.

## v3 design changes (local tests pass, not yet run on Kaggle)
- Correction allowance: each bounced submission grants +10 tool calls (max 2 rounds).
- New placebo condition **A_retry**: the first submit is bounced with a content-free
  "re-check" message plus the same +10 calls. It separates "extra chance and budget"
  from "verifier information".
- Runs: 7 × 4 conditions = 28.

## v3 — 2026-10-03 (7 tasks × A/A_retry/B/C, 28 runs; queued 33 min, ran 1 h 53 min)
| | A_prompt | A_retry | B_generic | C_domain |
|---|---|---|---|---|
| resolved | 1/7 | 2/7 | 1/7 | 1/7 |
Single seed: descriptive only. The correction allowance worked (tool calls up to 56), but
B/C still repeated the same failure across all rounds. The traces show why:

**Tool-interface confound (dominant failure, all conditions):**
- 62% of edit/write calls arrive one escaping level too deep. After `json.loads`, newlines
  are the two characters `\` `n` and quotes are `\"`, so exact `edit_file` fails (NoMatch)
  or writes literal `\n` into source (the G-SYNTAX failures in FSC-003/FSC-009).
- v3 edit_file outcomes: 106 ok / 293 NoMatch / 130 InvalidArguments / 8 MultipleMatches.
  Only 20% of edits succeeded.
- InvalidArguments (107 of 130): the gemma4 tool parser splits a mis-escaped argument,
  so code fragments become keyword names (`unexpected keyword argument 'state = …'`), or
  `old_string` goes missing.
- Knock-on effect: "gate says hygiene (stray repro.py) → agent deletes it → gate says
  *empty patch*". The source edits had never applied, so the gate's first message masked
  the real problem.
- Separately, 3/23 bounces were answered by re-submitting without any change ("submit
  spam").

**Fix (applied identically to every condition):** `pilot/edit_tiers.py`, a resilient
replacement modelled on the harness's 3-tier `apply_replacement` (source not inspected):
exact → one-level unescape → indentation-flexible → whitespace-token regex. `write_file`
content that looks double-escaped is unescaped once. Replay of the 301 failed v3 edits
against base files: **173 (57%) recover via the unescape tier, all parse**. 64 are
genuinely not found and 43 target files absent at base. Per-run tier counts
(`edit_tiers`) and `malformed_calls` are now recorded.

Open item: confirm the tiers against the actual `adk-eval-core` `apply_replacement`
(wheel in `metric/gemma-4-developer-agent-wheelhouse`). Until then, results carry the
caveat "harness-approximate editing".

## v4 — 2026-10-03 (7 tasks × 6 conditions, seed 0; ran 2 h 12 min)
| | A_prompt | A_know | A_retry | B_generic | C_domain | C_know |
|---|---|---|---|---|---|---|
| resolved | 2/7 | 4/7 | 4/7 | 3/7 | 3/7 | 4/7 |
Single seed, so descriptive only. The approximate edit tiers lifted resolve rates from
14–29% (v3) to 29–57%. Seven to twenty edits per condition were recovered by the unescape
tier. Only 4 tasks discriminated: FSC-007/014 were solved everywhere and FSC-009 nowhere.
FSC-006 was "½" in every condition.

## Post-v4 fixes (2026-10-03)
- **Harness-identical editing**: v4 captured the harness source. The engine is exact →
  flexible → regex → unescaped (1- or 2-level JSON) inside `adk_eval_core/editing/edit.py`;
  `swegemma/edit.py` wraps it with a diff response; `write_file` writes content verbatim.
  The runner now calls the installed `swegemma.edit.apply_replacement` (a local copy is used
  only for smoke tests) and records `edit_engine`. Our own `edit_tiers.py` is removed.
- **FSC-006 root cause**: the hidden test asserted the private `_sessions_for()` helper.
  Agents correctly closed off-hours sessions at the public gate (`open_symbols`) and
  failed anyway. Rewritten as behavioral tests at frozen times (after-market closed,
  extended opt-in open, regular open). The domain verifier was rewritten the same way.
  Re-scoring the v4 patches: 5/6 resolve, only A_know genuinely fails. FSC-007 has the same
  coupling. It did not bite in v4, but it is flagged for audit.
- **Task set expanded 7 → 20** (see task-candidates.md): FSC-002/005/015 (incidents; behavioral
  hidden tests replace private-API / wording-coupled originals), 3 control tasks, and 7
  injected/latent tasks (look-ahead, sell fee, future news *latent in current code*, A/B
  window, ATR floor, take-profit rebuy, priced-in sign). Visible tests that would expose an
  injected bug are moved into the hidden set automatically.

## v5 — 2026-10-03 (20 tasks × 6 conditions, seed 0; 07:39–14:09, 120/120 runs, 0 contaminated)
Kernel status ERROR came from the notebook's own Step-4 assert after all runs had finished:
it demanded an invariant brief for control tasks, which have none by design. The data is
intact and the assert is now fixed (controls exempt). All edits ran on the harness engine
(`edit_engine = swegemma`).

| | A_prompt | A_know | A_retry | B_generic | C_domain | C_know |
|---|---|---|---|---|---|---|
| resolved | 12/20 | 12/20 | 13/20 | 13/20 | 13/20 | **15/20** |

PRIMARY C_know vs A_know: +15 pp (CI −5…+35), discordant 4 / 1 (C_know-only: FSC-004,
FSC-005, INJ-02, INJ-05; A_know-only: INJ-04), placebo p = 0.18. Single seed, so descriptive
only. Every secondary contrast is within ±5 pp.
- Ceiling: 9 tasks were solved by all 6 conditions and 2 by none (FSC-C02, FSC-C03), so
  only 9/20 discriminate.
- Controls: C01 was solved everywhere and C02/C03 nowhere. As intended, domain feedback
  showed no edge there.
- Malformed tool calls remain large and rise with gating: 70–96 in A, 113–184 in B/C.
  Gates add turns, and every extra turn risks a parser-damaged call. Report this as cost
  and as a confound candidate.
- Next: seeds 1 and 2 with the identical config (next quota week) to get the noise floor
  and a decision under the pre-registered rule.

## v6 — seed 1 (queued 5 h 20 min, ran 19:45–02:42), merged with v5 → 240 runs, 2 seeds
| | A_prompt | A_know | A_retry | B_generic | C_domain | C_know |
|---|---|---|---|---|---|---|
| resolve (2 seeds) | 57.5% | 55.0% | 62.5% | 65.0% | 62.5% | **72.5%** |
Noise floor (min readable delta, pooled seed sd 4.1%, 2 seeds) = 8.0%.
**PRIMARY C_know vs A_know: +17.5 pp (CI +5…+30), discordant 8/1, placebo p = 0.015 →
"X beats Y" under the pre-registered rule.** Every secondary contrast is below the noise
floor, including C_domain vs B_generic (−2.5) and C_domain vs A_retry (0).
Reading: enforcement helps only when paired with stated invariants. Domain feedback alone
(C_domain) does not beat generic feedback or a content-free retry. Caveats: the floor
comes from just 2 seeds, and the seed-0 trace audit attributed only 1 of 4 C_know wins
directly to a domain-violation repair. Seed 2 is needed before the paper claim, plus a
mechanism audit of the merged discordant pairs.

### Mechanism audit of the 2-seed PRIMARY result (2026-10-04)
C_know and A_know are **identical up to the first submit_patch** (same prompts and same
invariant brief). Of the 8 C_know-only wins:
- 2 were domain repairs: FSC-005 (s0) and FSC-002 (s1). The gate flagged a D-* violation
  and the agent fixed it.
- 5 were hygiene-only bounces. The first-submit patch already passed every domain check,
  so the source fix was unchanged by the gate.
- 1 passed the gate on the first submit.
So 6 of 8 were decided before the gate could act. They reflect sampling differences
between independent runs, not the intervention. The 1 A_know-only case is INJ-04, where
C_know failed despite three domain bounces. The rule-level "X beats Y" therefore rests
mostly on chance, and the 2-seed noise floor (8 pp) likely understates run-to-run
variance.

**Design upgrade for seed 2 (kernel v8, agent behaviour unchanged):** every gated run now
stores its first submitted patch and scores it with the hidden tests
(`resolved_at_first_submit`). The causal effect of the gate becomes a within-run count:
first-submit unresolved → final resolved (gate rescued), and the reverse (gate harmed).
Between-run sampling noise disappears. This becomes the primary mechanism metric for the
paper, alongside the pre-registered between-condition rule.

## v8 — seed 2 (07:22–13:15) → 360 runs, 3 seeds merged
| | A_prompt | A_know | A_retry | B_generic | C_domain | C_know |
|---|---|---|---|---|---|---|
| resolve (3 seeds) | 60.0% | 58.3% | 63.3% | 68.3% | 66.7% | **73.3%** |
Noise floor 9.0% (pooled seed sd 5.7%, 3 seeds).
**PRIMARY C_know vs A_know: +15.0 pp (CI +3.3…+26.7), discordant 11/2, placebo p = 0.015 →
"X beats Y".** Every secondary contrast is below the floor.

**Within-run gate effect (seed 2, first-submit patch scored with hidden tests):**
| gated condition | rescued (first ✗ → final ✓) | harmed (first ✓ → final ✗) |
|---|---|---|
| A_retry (content-free bounce) | 0/20 | 0 |
| B_generic | 1/20 (FSC-005) | 0 |
| C_domain | 2/20 (FSC-003, FSC-006) | 0 |
| C_know | 2/20 (FSC-006, FSC-009) | 0 |
- The causal effect of an executable gate is real but small: +5–10 pp per seed, never
  harmful. A content-free retry rescues nothing.
- Seed 2: C_know's first-submit rate (13/20) equals A_know's (13/20), so the whole seed-2 gap
  (+10 pp) is the gate's rescues. On seeds 0–1, most of the gap was pre-gate sampling (audit
  above).
- Paper framing: report both, the between-condition rule (passes) and the within-run
  counterfactual (≈ +10 pp, 0 harm, informative feedback > content-free). The "knowing ×
  enforcing" interaction remains suggestive (C_domain rescues as often as C_know here).

## v9 design (2026-10-30) — public task FinSWE-21 and verifier re-audit (not yet run)
- **FinSWE-21 / PUB-21** (`tasks/PUB-21-ta-unpadded-date`): TradingAgents v0.7.0 (e8f5503).
  The model's unpadded `curr_date` passes `as_of` unchanged, and SEC EDGAR compares filing
  dates as text (PR #1488 comment, 2026-10-22). Gold is the date_window.py hunk of a5b0f21.
  Hidden tests are behavioural through `get_income_statement`, so a fix at either layer
  passes; a draft test that called the vendor's `_as_of` directly was dropped because it
  rejects upstream's own fix. Verifier `PUB-21.py` uses another filer, the balance sheet,
  other dates and a boundary probe.
- Harness: `task.json` may name `repo` / `pkg` / `code_dirs` / `env`. Public tasks are
  materialized from `../public-src/<repo>` and never sanitized, and they run on their own
  venv (`harness/public_task.py setup|build|wheels`). On Kaggle the venv is built offline
  from the `finswe-tradingagents-wheels` dataset and goes first on PATH for agent commands.
- Re-audit (writeup §3.4 design rule): INJ-03 + **D-PIT-3** (pubDates in +09:00 / −05:00,
  ±1 min around T). A naive wall-clock comparison passed D-PIT-1/2 and fails D-PIT-3
  (checked against a stand-in `parse_headlines`). INJ-01 + **D-LOOK-3** (open ≠ close):
  kit candles have open = close, so a next-bar-close fill was indistinguishable from the
  correct next-bar-open fill. Selftest on the private source is pending. The 360 reported
  runs used the original verifiers.
- Kernel v9: `CFG["tasks"] = ["PUB-21-ta-unpadded-date"]`, seeds 0–2, 18 runs (≈1 h at
  ~3.1 min/run). Results go to their own `results.jsonl` and are never merged with v5–v8.

## v9 / v10 — 2026-10-30 (FinSWE-21 / PUB-21 × 6 conditions × seeds 0–2, 18 runs, 0 contaminated)
- Local checks (user's PC): `public_task.py build` VALID (1366 tests; F2P 3, P2P 1362, gold failures 0).
  Selftest all OK; one INJ-02 run segfaulted in the interpreter (rc −11, a known random fault on
  that PC) and passed when repeated.
- v9 stopped in the CPU setup cell: the image's Python (3.12.13) has no `ensurepip`. Fixed in
  92d644f (bare venv, image pip with `--python`). v10 completed. The venv was under
  /kaggle/working, which made `kaggle kernels output` crawl; moved to /tmp in 478196a.

| | A_prompt | A_know | A_retry | B_generic | C_domain | C_know |
|---|---|---|---|---|---|---|
| resolved | 1/3 | 2/3 | 0/3 | 0/3 | **3/3** | **3/3** |
| within 40 calls | 1/3 | 2/3 | 0/3 | 0/3 | 3/3 | 1/3 |
| first ✗ → final ✓ | – | – | 0/3 | 0/3 | 3/3 | 2/2 |

- C_domain: every first submit failed D-PIT-SEC-1/2 and was repaired after feedback; one run
  also tripped D-PIT-SEC-3 in round 2.
- B_generic: the generic gate passed all three; all failed the hidden tests (the FSC-014
  pattern).
- C_know: two wins used 42 calls; one first submit failed G-SYNTAX + D-IMPORT.
- Noise floor 53 pp; PRIMARY +33 pp, placebo p 0.50: descriptive only (`results/v10/analysis.md`).
- Correction after reading `gate_rounds`: every D-PIT-SEC flag in C_domain (9/9) and in C_know
  seed 1 round 1 has status `error`. The patched code raised inside the tool call, and no late
  filing was observed. Only C_know seed 1 round 2 is a true `fail`. Writeup §5.4 says so. The
  traces (not downloaded; Kaggle 429) would show the exception. A likely cause is a patch that
  rejects unpadded dates: langgraph's ToolNode re-raises non-invocation errors, and the issue
  requires the earlier filing to still be served.
- Environment noise: the venv interpreter prints "Error in sitecustomize … No module named
  'wrapt'". It comes from the Kaggle image's sitecustomize. It appears in every PUB-21 arm
  equally, and probably in the agents' command output too. For the next run, add `wrapt` to the
  wheel set.
- Malformed tool calls: A_prompt 27, A_know 27, A_retry 11, B/C 0. This is the opposite of the
  core runs. n = 3 per arm, so it is not interpreted.
- Traces (`results/v10/first-round-errors.md`): every `error` was the agent's own parsing code
  crashing on the check's unpadded date (`date.fromisoformat('2025-3-7')` → ValueError;
  `datetime.datetime.strptime` under `from datetime import datetime` → AttributeError; one
  SyntaxError from literal `\n` escapes). None came from the environment. Every passing patch
  fixed `sec_edgar._as_of`, and none touched `date_window.py` (upstream's fix location). The
  behavioural hidden tests were needed to score these runs as resolved. All three B_generic
  final patches use `fromisoformat`, which passes the visible tests and fails the hidden ones.
- Follow-up: `public_task.py wheels` now adds `wrapt` (`KAGGLE_IMAGE_EXTRAS`) to the
  wheel set. The `finswe-tradingagents-wheels` dataset was versioned on Oct 30 with it
  (93 wheels, wrapt 2.5.2; offline install into a bare venv imports `wrapt` and `langgraph`).

## Kernel v11 → v12 (Oct 30): scratch-file contradiction, PUB-21 evidence

- v11 (wheels with wrapt; `results/v11/`): no agent trace contains `Error in sitecustomize`.
  Resolved of 3: A_prompt 2, A_know 2, A_retry 1, B_generic 1, C_domain 1, C_know 3.
- In all 18 v11 runs the first `write_file('/tmp/repro.py')` was refused ("path outside
  /workspace"): `system.md` and the G-HYGIENE message said scratch files belong in /tmp, but
  `write_file`/`edit_file` reach /workspace only. Agents then wrote `/workspace/repro.py`, so
  all 9 gated runs spent their first bounce on G-HYGIENE, and 8 ungated final patches kept
  `repro.py`. v12 changes the prompt ("create scratch files with `run_command`") and the
  G-HYGIENE message ("delete it with `rm`"). The core 360 runs used the old wording.
- PUB-21's verifier reported the last 160 characters of the tool output as `observed`, which
  never contained the served value. It now reports the cutoff header and the Total Assets row
  (e.g. `… filed on or before 2025-3-7 … | Total Assets,6989`). In v11, C_domain s0 repeated
  identical edits five times after that feedback.

## Kernel v12 → v13 (Oct 31): context overflow, repeated parser-damaged calls

- v12 (`results/v12/`): stray-file G-HYGIENE bounces fell from 9 gated runs to 2, and
  `repro.py` in final patches from 8 to 1. Resolved of 3: A_prompt 2, A_know 1, A_retry 1,
  B_generic 0, C_domain 2, C_know 3.
- A_prompt s0 ended on `llm_error`: 24,577 prompt tokens + `max_tokens` 8,192 > 32,768, and
  compaction had no tool output left to elide. `vllm_policy` now retries such a request once
  with the output room that is left (≥ 1,024 tokens).
- Seed-2 A_retry, B_generic and C_domain re-sent one parser-damaged `edit_file` call
  (`old_string` folded into `new_string`) 30–50 times verbatim. B_generic s2 and C_domain s2
  never applied an edit. An identical malformed call now gets a hint naming the arguments the
  tool received, and suggesting `run_command`. Run records count these as `repeated_malformed`.
- v13 (`results/v13/`): all 18 runs ended by submitting. No `llm_error` (v12: 6 events in 4
  runs, one of which ended on it). One malformed call in all runs and no repeats, so the
  repeated-call hint never fired; v13 cannot show whether it helps. Resolved of 3:
  A_prompt 1, A_know 1, A_retry 2, B_generic 2, C_domain 3, C_know 2. Every contrast is
  below the noise floor (84 pp).
