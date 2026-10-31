# FinSWE-21 runbook (user PC → Kaggle → paper)

The cloud session can't reach Kaggle and can't install TradingAgents, so these steps run on
the PC that holds `ai-trader` (sibling directory of this repo).

1. **Public task build (network needed)**
   ```bash
   python harness/public_task.py setup --task PUB-21-ta-unpadded-date   # ../public-src/TradingAgents + venv
   python harness/public_task.py build --task PUB-21-ta-unpadded-date   # must print VALID; fills eval.json P2P
   python harness/verify.py selftest --task PUB-21-ta-unpadded-date     # base flagged, gold clean
   ```
2. **Re-audited verifiers (private source)**
   ```bash
   python harness/verify.py selftest   # expect 17/17 OK (+ PUB-21); INJ-01 now has D-LOOK-3, INJ-03 has D-PIT-3
   ```
3. **Wheels for the offline kernel.** Use the Kaggle image's Python version (check `python --version` in the kernel):
   ```bash
   python harness/public_task.py wheels --task PUB-21-ta-unpadded-date --python-version 3.11
   kaggle datasets create -p dist/tradingagents-wheels      # private: kmmmvs/finswe-tradingagents-wheels
   ```
4. **Dataset + kernel**
   ```bash
   python pilot/export_dataset.py && kaggle datasets version -p dist/finswe-pilot-data -m "v9: PUB-21, D-PIT-3, D-LOOK-3"
   python pilot/build_notebook.py && kaggle kernels push -p pilot      # CFG: tasks=[PUB-21], seeds 0–2 → 18 runs
   ```
5. **Back to the paper.** Download `results.jsonl` (v9 only, never merged with v5–v8) and fill
   the `[KAGGLE]` slots in `paper/writeup-v2.md` §5.4 (resolved per arm out of 3; first ✗ → final ✓
   for gated arms), then remove the `[TODO]` markers in §3.2 and §3.4.

**Watch on the first runs:** G-REGRESSION runs the whole TradingAgents suite (~1,270 tests) at
every gated submit. If one suite run takes more than a minute or two in the kernel, gated arms lose
much more of the 12-minute clock than on the core tasks. Note the per-gate time in the v9 log
before reading the arm differences.
