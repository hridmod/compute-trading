# Compute Trading

Empirical test suite for the thesis that GPU compute is commoditizing the
way oil and power did. See [`PROJECT_BRIEF.md`](PROJECT_BRIEF.md) for the
full thesis and sub-project roadmap.

## Sub-projects

- [`token_parity/`](token_parity/) — tests whether GPU rental price ever
  exceeds what the tokens that GPU can serve are worth on the open market
  (the "token-parity ceiling"). Live-pulled data, daily automated snapshots
  via GitHub Actions, accumulating backtest. **Built.**
- [`substitution_ceiling/`](substitution_ceiling/) — tests whether legacy
  GPUs (H100, H200) rent for more than their relative throughput vs. the
  best available chip (B200) justifies. Live-pulled, no LLM pricing basket
  needed. **Built.**
- [`shutdown_floor/`](shutdown_floor/) — tests whether GPU rental price
  ever sustainably prints below the marginal operator's variable cash cost
  (power draw x datacenter PUE x industrial electricity rate). Closes out
  all three forward-curve anchors from the thesis. **Built.**
- [`neocloud_credit_stress/`](neocloud_credit_stress/) — structural credit
  model for a real GPU-collateralized loan (CoreWeave's $2.6B facility,
  1.35x DSCR covenant): deterministic scenarios plus a Monte Carlo
  comparison of three rate-decay processes. **Built.**

Each sub-project is self-contained and runnable on its own, e.g.:

```
cd token_parity
pip install -r requirements.txt
python analysis/run_analysis.py
```
