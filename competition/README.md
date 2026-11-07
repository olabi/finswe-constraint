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
