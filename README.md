# Compute Trading

Empirical test suite for the thesis that GPU compute is commoditizing the
way oil and power did. See [`PROJECT_BRIEF.md`](PROJECT_BRIEF.md) for the
full thesis and sub-project roadmap.

## Sub-projects

- [`token_parity/`](token_parity/) — tests whether GPU rental price ever
  exceeds what the tokens that GPU can serve are worth on the open market
  (the "token-parity ceiling"). Live-pulled data, daily automated snapshots
  via GitHub Actions, accumulating backtest. **Built.**

Each sub-project is self-contained and runnable on its own:

```
cd token_parity
pip install -r requirements.txt
python analysis/run_analysis.py
```
