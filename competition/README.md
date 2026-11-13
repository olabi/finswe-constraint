# Competition entry: gemma-4-developer-agent

The Kaggle competition [gemma-4-developer-agent](https://www.kaggle.com/competitions/gemma-4-developer-agent)
takes a declarative submission: YAML agent configs, prompts and LoRA adapters, compiled by the
host's `adk-submission` (HARNESS_README §2). Python entry points are not accepted, so the pilot
runner and its offline enforcement switches (`pilot/finswe_pilot.py`) cannot be submitted as
code. What carries over is what the pilot validated:

| Setting | Here | Official sample | Source |
|---|---|---|---|
| System prompt | `pilot/system.md` plus two lines (analyzer tool, no whole-repo test runs) | baseline prompt | paper Section 4 |
| Budget | 40 tool calls, 12 min, 300 s per command, 80 turns | 10 calls, 1 min | paper Section 4 |
| Sampling | temperature 0.2, top-p 0.95, top-k 40, 8,192 output tokens, thinking off | 16,384 tokens, thinking 4,096 | paper Section 4 |
| Agent tree | coder + read-only analyzer as an AgentTool, sample LoRA adapters | same | sample_submission |

The process rules that `Budget.enforce_*` enforced in the pilot appear here as prompt rules only;
Section 5.5 of the paper found that enforcing them did not change resolution. The harness itself
strips test and runner-config files from every patch (HARNESS_README §8.1).

## Build

```bash
python3 competition/build_submission.py --sample <competition data>/sample_submission --out submission.zip
```

The adapters come from the competition's `sample_submission/adapters/` and are not stored here.
The script checks the host's documented limits and writes the zip; it never submits.
Submitting (`kaggle competitions submit`) is an outward action that needs the user's go-ahead (C6).

## Submissions

| Date | Kaggle id | Package | Public score |
|---|---|---|---|
| 2026-11-07 | 58076537 | v1 `competition/submission` (repo 270e19a) | 0.08 |
| 2026-11-08 | 58125674 | v2 `competition/submission_v2` (repo f861fd6) | pending |

Earlier entries from this account (2026-09-28 to 09-30, GUAM AGT-01) all scored 0.00.

**The uploaded file must be named `submission.zip`.** The same v2 archive uploaded as
`submission_v2.zip` was refused twice with `400 Bad Request` from `CreateSubmission`, with no
reason given; renamed to `submission.zip`, it was accepted at once. Keep `--out` pointing at a
file called `submission.zip` (in a separate folder per version).

## v2 (`competition/submission_v2`)

v2 starts from the public notebook "Gemma 4 | Budget-Aware Coding Agent - Efficient Navigation",
which adapts matterhorn3838's "Gemma 4 SuperAgent"
(https://www.kaggle.com/code/matterhorn3838/gemma-4-superagent). That line of configs scores
about 0.18–0.22 on the public leaderboard, and its prompt is used here with credit. v1 differs
from it in four ways: an extra sub-agent with graph tools, thinking off, LoRA adapters, and
40 calls / 12 min (the public notebook keeps 28 calls / 8 min inside the global 12-hour limit).
v2 keeps the public configuration and changes two things:

1. **The graph tools are not declared.** The public prompt forbids them ("they return nothing
   useful"), but declaring them makes the harness advertise them in the first message.
2. **The final check deletes stray untracked files.** The FinSWE-Constraint pilot showed agents
   leaving scratch files in the repository even when told not to (6 of 7 tasks; 41 of 60 gated
   core runs bounced on hygiene), and untracked files are part of the submitted patch.

```bash
python3 competition/build_submission.py --src competition/submission_v2 --out v2/submission.zip
```

## v3 (`competition/submission_v3`, not yet submitted)

v3 is v2 plus two prompt rules, prompted by the paper-track writeup "TwinBench" (R. Saxena,
CC BY 4.0), which reports that models recite a rule that conflicts with their priors and then
answer by the prior anyway:

1. **Issue over prior.** When the issue asks for something unusual (an odd default, a reversed
   order, an exception to a common rule), implement what it says.
2. **Mechanical literal check.** v2 asks the agent to confirm from memory that every name and
   message from the issue appears in the patch. v3 makes it run `git diff | grep -cF` for those
   literals, so the check is executed instead of recalled.

These are prompt rules, not enforced by the harness, and v3 has not been scored. v2's score was
not known when v3 was written, so the two changes are untested on top of an untested base.

```bash
python3 competition/build_submission.py --src competition/submission_v3 --out v3/submission.zip
```
