# AGENTS.md: the contract for anyone who changes this repository

This file is the single source of truth for how this repository is changed. It binds every
author, whether a person, Claude Code, or any other coding agent. It follows the structure
of the GUAM team's `AGENTS.md` (reading map, naming standard, PR checklist). It differs in
one respect: **every clause names the check that enforces it, and a failing check blocks
the change.** Reading a rule is not the same as following it, which is this paper's own
finding.

**Signing.** A pull request signs the contract with the version it read:

    Contract: AGENTS.md@<first 8 hex of sha256(AGENTS.md)>

`python3 tools/contract_check.py --version` prints that line. CI rejects a pull request whose
signature does not match the `AGENTS.md` in that pull request. A contract that changed since
it was read must be read again.

---

## 1. Read before you start: where each answer lives

| What you need | Source of truth |
|---|---|
| What the paper claims, and the printed numbers | `paper/writeup.md` |
| How every number is recomputed | `repro/reproduce.py`, `repro/expected.json`, `repro/README.md` |
| The pre-registered analysis | `paper/analysis-plan.md`, `pilot/analyze.py` |
| Tasks, hidden tests, verifiers | `tasks/`, `harness/`, `paper/verifier-design.md` |
| Run history and what changed between kernels | `paper/pilot-log.md`, `results/` |
| What is deliberately not in this repository | `README.md`, section "What is not here" |

**Rule 0: sync before you claim.** Before saying something is missing or unimplemented,
run `git fetch origin && git status`. An analysis on a stale checkout is wrong in full.

## 2. Naming standard

| What | Format | Example |
|---|---|---|
| Pull-request title | `[<AREA>] <summary>` | `[PAPER] Report FinSWE-21 across kernels v10–v13` |
| Commit subject | `<type>: <AREA> <summary>` | `fix: REPRO SHA256SUMS covers run records only` |

- `<type>` ∈ `feat | fix | refactor | test | docs | chore` (Conventional Commits, as in GUAM).
- `<AREA>` ∈ `PAPER | REPRO | RESULTS | HARNESS | TASKS | PILOT | DATA | CONTRACT`, or a
  task id such as `PUB-21` or `FSC-001`.
- A merge commit made by GitHub is exempt.

## 3. Clauses

| ID | Clause | Enforced by |
|---|---|---|
| C1 | **No answers in the repository.** No gold or bug patch of a core task (`tasks/{FSC,INJ}-*/gold*.patch`, `bug.patch`), no core trajectories (`traces.zip`), no bug-injection script. FinSWE-21 (`tasks/PUB-*`) may ship its upstream gold. | `contract_check.py` |
| C2 | **No secrets and no third-party material we may not redistribute.** No keys, tokens, `.env*`, `pilot/_vendor/`, `harness_src/`, or collected news text (`data/**/*_news.json`). | `contract_check.py` |
| C3 | **Every printed number is recomputed.** `python3 repro/reproduce.py` ends in ALL MATCH, and the paper's result tables equal `repro/expected.json`. If results change, change `expected.json` and `paper/writeup.md` together, in the same pull request. | `contract_check.py` (runs reproduce.py, compares the tables) |
| C4 | **Run records are checksummed.** Every file listed in `results/SHA256SUMS` matches, and every `results/**/results.jsonl` is listed. After a new run record, run `python3 repro/checksums.py` in the same pull request. | `contract_check.py` |
| C5 | **The paper fits its submission form.** Subtitle ≤ 140 characters (Kaggle's limit). No editorial markers (`[REV]`, `[TODO]`, `[VERIFY]`, `[KAGGLE]`) in `paper/writeup.md`. | `contract_check.py` |
| C6 | **Outward actions need the user's explicit go-ahead in the same conversation.** These are a Kaggle submission, a dataset or kernel upload, a push or pull request to any other repository (ModulabsRAPIDSLAB/GUAM and its forks included), and a repository visibility change. | `.claude/hooks/contract_gate.py` turns these commands into an approval prompt |
| C7 | **The pull request carries the signed checklist.** It uses `.github/pull_request_template.md`, every box is ticked, and the signature matches. | CI job `contract` |
| C8 | **Claims match evidence.** A sentence that reports a number points to where it is computed (`repro/`, `results/`, `pilot/analyze.py`). Write "post hoc" or "descriptive" when the pre-registered rule does not cover it. | review; C3 catches the numbers |
| C9 | **Names follow §2.** The pull-request title and every commit subject in the pull request match the naming standard. | CI job `contract` |

## 4. Pull-request checklist (mirrors `.github/pull_request_template.md`)

- [ ] C1–C5: `python3 tools/contract_check.py` → ✓ contract holds
- [ ] C6: no outward action without the user's go-ahead
- [ ] C7: every box ticked, signature line pasted from `--version`
- [ ] C8: numbers in the text point to where they are computed
- [ ] C9: title `[<AREA>] …`, commits `<type>: <AREA> …`

## 5. How the contract is enforced

- **Before a command runs (local, Claude Code).** `.claude/settings.json` runs
  `.claude/hooks/contract_gate.py` before every Bash command.
  - `git commit` and `git push` are refused while `contract_check.py` fails (C1–C5).
  - Every C6 command becomes an approval prompt, whatever the permission mode.
- **On every pull request (GitHub Actions).** `.github/workflows/contract.yml` runs
  `contract_check.py` with the PR body, title and commit range. It re-runs when the body or
  title is edited, and fails on any violation of C1–C5, C7 or C9.
- **At merge (repository owner).** Make the `contract` check *required* on `main`
  (Settings → Branches or Rules → require status check `contract`). Without that, CI reports
  a failure but cannot block the merge.
- **Human review** stays the last gate, as GUAM's Owner review is. It covers C8 and whatever
  no script can judge.
