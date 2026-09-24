# token_parity

Tests hypothesis #6 from `PROJECT_BRIEF.md`: the **token-parity ceiling**.

> A rational inference operator won't pay more per GPU-hour to rent hardware
> than the tokens that hardware can serve are worth on the open market:
>
> `rental $/hr <= (tokens/hr the GPU can serve) x (market $/token)`

## Model

```
ceiling_usd_per_hr = offline_tokens_per_sec_per_gpu * 3600 * market_usd_per_completion_token
ratio = rental_usd_per_hr / ceiling_usd_per_hr        # > 1.0 = ceiling violated
```

- **Throughput** (`offline_tokens_per_sec_per_gpu`): MLPerf Inference, Llama2-70B,
  *offline* scenario (max achievable throughput, not latency-constrained — the
  most generous ceiling). Per-GPU, derived from official 8-GPU closed-division
  submissions.
- **Market rate** (`market_usd_per_completion_token`): median output-token price
  across a fixed basket of comparable-capability (~70B-class) instruct models
  currently served via API, pulled live from OpenRouter.
- **Rental rate** (`rental_usd_per_hr`): median on-demand $/hr across live,
  verified, single-GPU offers, pulled live from Vast.ai.

## Assumption flagged explicitly

MLPerf still benchmarks **Llama2-70B** specifically, but that exact model is
no longer commonly metered/served via API — the market has moved to
Llama-3.x/Qwen-2.5/etc. So the "market $/token" leg is a **basket proxy**
(`src/pull_llm_pricing.py::MODEL_BASKET`) for "~70B-class constant capability
tier," not literally Llama2-70B pricing. If you think a tighter proxy exists,
swap the basket — it's a plain list, not a scraped/fuzzy match, specifically
so it's easy to audit and change.

## Data

| File | Nature | Source |
|---|---|---|
| `data/mlperf_benchmarks.csv` | Static, curated, sourced+dated | MLCommons/NVIDIA official MLPerf Inference v4.1/v5.0 submissions |
| `data/gpu_rental.csv` | Live, overwritten each run | Vast.ai public bundles API (no auth) |
| `data/llm_pricing.csv` | Live, overwritten each run | OpenRouter public models API (no auth) |
| `data/history/ceiling_snapshots.csv` | Appended every run, never overwritten | derived (this repo) |

MLPerf throughput is kept as curated/static rather than live-pulled: results
are only published a few times a year (not on a schedule you'd poll), and
MLCommons doesn't expose a simple pricing-style JSON endpoint for them.

**Benchmark integrity note**: the source thesis material cites H100
Llama2-70B throughput "ranging from ~3,000 to ~24,525 tok/s across sources."
Tracing this down: both numbers come from the *same* NVIDIA MLPerf v4.1
submission (24,525 tok/s offline across an 8-GPU DGX H100 system) — one is
just that total divided by 8 (~3,066/GPU), the other is the raw 8-GPU
system total cited without stating the GPU count. That's not independent
cross-vendor disagreement, it's secondary sources dropping normalization
context. Both rows are kept in `mlperf_benchmarks.csv` (see the `notes`
column) rather than silently resolved, per this repo's working convention —
the model only ever uses the `normalization == per_gpu` row.

## Running it

```
pip install -r requirements.txt
python analysis/run_analysis.py          # pulls live data, runs the test, appends a history snapshot
python analysis/run_analysis.py --no-pull  # reuse cached data/*.csv, skip the live pull
python analysis/backtest.py              # report the ratio across all accumulated history
```

## Automated data pulling

`.github/workflows/daily_snapshot.yml` runs `run_analysis.py` daily via
GitHub Actions and commits the updated `data/` back to the repo — this is
what turns the single cross-sectional snapshot below into an actual
time-series backtest over time. Trigger it manually anytime via
"Run workflow" in the Actions tab.

## First result (2026-09-24 live pull)

| GPU | rental $/hr (median) | ceiling $/hr | ratio | violation |
|---|---|---|---|---|
| H100 SXM | 3.51 | 4.42 | 0.80 | No |
| H200 SXM | 5.00 | 6.30 | 0.79 | No |
| B200 | 9.39 | 17.79 | 0.53 | No |

**No ceiling violations** — consistent with the null result flagged when
this sub-project was first scoped. But the ratio is notably tighter than the
originally-cited 5-40%: on today's live data the ceiling binds at 53-80% for
all three SKUs, with H100/H200 the closest. That's a real shift worth
watching — either token prices have fallen further, rental prices have
firmed, or both. This is exactly what `backtest.py` is for once daily
snapshots accumulate.

**Honest limitation**: this is one snapshot. A real backtest needs
accumulated history — `backtest.py` says so explicitly when it only finds
one date, rather than presenting a single point as a trend.

## Open next steps

1. Let the GitHub Action accumulate daily snapshots for a few weeks, then
   re-read `backtest.py` output for an actual time-series read (does the
   ratio trend toward 1.0, or stay range-bound?).
2. Segment `gpu_rental.csv` by provider type (serverless API host vs. raw
   GPU-hour marketplace) — the ceiling should bind tightest for pure-decode
   inference deployments and be closer to irrelevant for training-heavy
   rentals, which Vast.ai's on-demand marketplace is mostly used for today.
3. Extend `MODEL_BASKET` / `mlperf_benchmarks.csv` to a second benchmarked
   model (e.g. Mixtral-8x7B, also in MLPerf) to check whether the ratio
   result is sensitive to the Llama2-70B proxy choice.
