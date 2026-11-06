# CLAUDE.md

You work under the contract in [AGENTS.md](AGENTS.md). Read it before changing anything.

- `.claude/hooks/contract_gate.py` runs before every Bash command. It refuses `git commit` and
  `git push` while `python3 tools/contract_check.py` fails. Fix the violation it reports; do not
  work around the hook.
- Kaggle submissions and uploads, pushes or PRs to other repositories, and visibility changes
  become an approval prompt. Ask the user in the conversation first (C6).
- A pull request uses `.github/pull_request_template.md`, ticks every clause, and carries
  the line printed by `python3 tools/contract_check.py --version`.
- Names follow AGENTS.md §2: PR title `[<AREA>] <summary>`, commit `<type>: <AREA> <summary>`.
