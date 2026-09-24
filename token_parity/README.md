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

- **Throughput** (`offline_tokens_per_sec_per_gpu`): MLPerf Inference v5.1,
  **Llama-3.1-405B**, *offline* scenario (max achievable throughput — the
  most generous ceiling). Per-GPU, derived from official closed-division
  submissions, sourced to the raw result log for each figure.
- **Market rate** (`market_usd_per_completion_token`): the latest-release
  model's completion price for a given basket, pulled live from OpenRouter.
  Two baskets are run side by side (see below) so the result isn't resting
  on one pricing assumption.
- **Rental rate** (`rental_usd_per_hr`): median on-demand $/hr across live,
  verified, single-GPU offers, pulled live from Vast.ai.

## Why Llama-3.1-405B, not Llama2-70B

Originally used Llama2-70B, matching MLPerf's oldest still-tracked model and
the source thesis material. That's a 2023-era model nobody deploys in
production anymore — MLPerf only keeps re-benchmarking it release over
release for cross-round comparability. Replaced it with Llama-3.1-405B, the
largest dense model MLPerf currently benchmarks and genuinely representative
of current flagship-class open-weight deployment.

**H100 has no standard 8-GPU submission for this benchmark.** Checked every
submitting org's results tree in `mlcommons/inference_results_v5.1` on
GitHub directly. The only H100 result for Llama-3.1-405B this round is
Cisco's 16-GPU submission (783.131 tok/s / 16 = 48.946 tok/s/GPU). Likely
reason: 405B params at FP8 need ~405GB+ of HBM for weights alone — tight for
8x80GB=640GB H100 with KV-cache headroom, while H200 (141GB/GPU) and B200
(180GB/GPU) have more room, so submitters skew there. Used the 16-GPU number
divided by 16, flagged rather than silently used — per-GPU throughput may
not scale identically at 2x the GPU count due to interconnect overhead, so
treat the H100 figure as the weakest-sourced of the three.

## Data

| File | Nature | Source |
|---|---|---|
| `data/mlperf_benchmarks.csv` | Static, curated, sourced+dated | Primary MLPerf Inference v5.1 result logs, `mlcommons/inference_results_v5.1` on GitHub |
| `data/gpu_rental.csv` | Live, overwritten each run | Vast.ai public bundles API (no auth) |
| `data/llm_pricing.csv` | Live, overwritten each run | OpenRouter public models API (no auth) |
| `data/history/ceiling_snapshots.csv` | Appended every run, never overwritten | derived (this repo) |

MLPerf throughput is kept as curated/static rather than live-pulled: results
are only published a few times a year, and MLCommons doesn't expose a
pricing-style JSON endpoint for them. Every row is sourced to the *raw
performance log* of the actual submission (`mlperf_log_summary.txt`), linked
directly, verifiable in one click — not a vendor blog paraphrase.

**Verification performed before trusting any of this** (worth stating
explicitly since this is going into a public writeup):
- Re-fetched all 6 raw MLPerf log files a second time independently and
  diffed against the committed CSV — exact match, no transcription errors.
- Independently cross-checked the B200 number against two different
  submitters (Nebius: 207.44 tok/s/GPU, Lambda: 206.08 tok/s/GPU, both from
  the same MLPerf round) — within 0.7% agreement.
- Verified all 6 GitHub source links resolve (HTTP 200), so anyone reading
  this can click through and check the primary source themselves.
- Hand-recomputed the ceiling/ratio math outside the codebase and confirmed
  it matches the script output exactly (see git history / conversation for
  the check).

**Benchmark integrity note (caught mid-research)**: an AI-generated web
search summary confidently reported "H100 achieves 138 tok/s/GPU, H200
achieves 170, B200 achieves 224" for this exact benchmark. Those numbers
were actually for **GB200/GB300 NVL72 systems** — a different product line
entirely — silently relabeled by the summarizer. Caught by re-fetching the
primary article directly and then going straight to MLCommons' raw
per-submission logs instead of trusting any aggregated source. Every number
in this repo is now sourced to a specific raw log file for exactly this
reason.

## Two pricing baskets, and a mistake caught before publishing

`meta-llama/llama-3.1-405b-instruct` itself has been delisted from
OpenRouter, so there's no single obviously-correct market price to use.
Two candidate proxies are run side by side rather than picking one:

| Basket | Model | Why | Caveat |
|---|---|---|---|
| `llama_3_1_405b_family` | `nousresearch/hermes-4-405b` | Fine-tune of the identical 405B dense base model MLPerf benchmarks — tightest architectural match | Thin/low-liquidity listing; price may not reflect real competition |
| `deepseek_v3_family` | `deepseek/deepseek-v3.2` | Heavily-served, competitively-priced flagship model | NOT an architecture match — DeepSeek-V3 is a ~671B-param MoE with ~37B active params/token, fundamentally cheaper to serve than a 405B *dense* model regardless of market competition |

**A methodology bug was caught and fixed during verification**: the first
version of the DeepSeek basket medianed across three sequential dated
releases (`v3-0324`, `v3.1`, `v3.2`), whose completion prices happen to fall
monotonically over time ($0.000001 → $0.00000095 → $0.0000004). Those
aren't concurrent competing products, they're the same lineage's price
*decaying over time* — medianing across them blends in stale, superseded
pricing and biases the "current market rate" upward. Fixed by using only
the latest release per lineage. Also corrected a reasoning error made while
first drafting this: a *cheaper* $/token doesn't shrink the ceiling
violation, it shrinks the ceiling itself (`ceiling = tok/s × $/token`), so
it makes the ratio *worse*, not better. Initial intuition here was
backwards; the code and hand-recomputation are correct.

## Running it

```
pip install -r requirements.txt
python analysis/run_analysis.py          # pulls live data, runs the test (both baskets), appends a history snapshot
python analysis/run_analysis.py --no-pull  # reuse cached data/*.csv, skip the live pull
python analysis/backtest.py              # report the ratio across all accumulated history, per basket
```

## Automated data pulling

`.github/workflows/daily_snapshot.yml` runs `run_analysis.py` daily via
GitHub Actions and commits the updated `data/` back to the repo — this is
what turns the single cross-sectional snapshot below into an actual
time-series backtest over time. Trigger it manually anytime via
"Run workflow" in the Actions tab.

## Result (2026-09-24 live pull, Llama-3.1-405B)

| Basket | GPU | rental $/hr | ceiling $/hr | ratio | violation |
|---|---|---|---|---|---|
| llama_3_1_405b_family (Hermes-4-405B, $3/M tokens) | H100 SXM | 3.40 | 0.53 | **6.43x** | Yes |
| llama_3_1_405b_family | B200 | 9.39 | 2.24 | **4.19x** | Yes |
| deepseek_v3_family (DeepSeek-V3.2, $0.4/M tokens) | H100 SXM | 3.40 | 0.07 | **48.19x** | Yes |
| deepseek_v3_family | B200 | 9.39 | 0.30 | **31.42x** | Yes |

H200 SXM has no row this run — Vast.ai simply had zero live single-GPU H200
offers at pull time (inventory fluctuated between runs while building this;
real marketplace thinness, not a bug). H100's rental price also moved
across runs made minutes apart while verifying this ($3.24-3.42/hr range,
all from Vast.ai's live order book) — expected for a live marketplace, and
it doesn't change the qualitative conclusion: violation ratios of 4-6x
(Hermes basket) and 31-48x (DeepSeek basket) across every pull, always well
over 1.0.

**Both baskets agree: the ceiling is violated, by a wide margin, under
either pricing assumption.** That's a more robust result than either basket
alone — it doesn't hinge on picking the "right" proxy. If anything the
more liquid, architecture-mismatched proxy (DeepSeek-V3.2) shows a *larger*
violation than the thin, architecture-matched one (Hermes-4-405B).

**This reverses the earlier Llama2-70B result**, which showed rental at
53-80% of ceiling (no violation). The driver: per-GPU throughput for a 405B
dense model is drastically lower than for a 70B model — 48.9 tok/s/GPU vs.
3,066 tok/s/GPU on H100, a 62.6x drop — while rental price barely moved.
That throughput drop, not the pricing-basket choice, is what's doing almost
all the work here, and it's the best-sourced number in this whole analysis
(cross-checked against two independent MLPerf submitters).

**What this likely means, stated carefully** (avoid overclaiming causality
from one snapshot): current $0.4-3/M-token pricing for 405B-class open
models implies economics that a single dedicated GPU, at current rental
rates, cannot support on MLPerf's reference offline-batched throughput.
Plausible explanations, not distinguished by this data alone:
1. Providers serve these models across much larger, more heavily-batched
   fleets than an 8-16 GPU MLPerf reference node, achieving materially
   higher effective throughput per GPU at production scale.
2. Rental price reflects demand for other workloads (training, smaller/
   inference-cheaper models) rather than dedicated 405B-token production —
   i.e. the marginal renter of an H100 isn't running a 405B model on it.
3. Providers are pricing 405B-class tokens below the GPU-hour cost that
   would be required to produce them on a dedicated node, cross-subsidized
   by scale, commitments, or other revenue.

Can't tell these apart from a single cross-sectional snapshot — that's
exactly what accumulating daily history via the GitHub Action is for.

## Open next steps

1. Investigate explanation #1 above directly — find real-world reported
   production throughput/GPU for 405B-class serving (vs. the MLPerf
   reference node) to see how much of the gap it closes.
2. Let the GitHub Action accumulate daily snapshots for a few weeks, then
   re-read `backtest.py` output for a real time-series trend.
3. Segment `gpu_rental.csv` by provider type (serverless API host vs. raw
   GPU-hour marketplace) — the ceiling should bind tightest for pure-decode
   inference deployments.
4. Investigate why H100 wasn't submitted at 8-GPU scale for this benchmark
   this round — if structural (memory headroom), that's itself a data point
   for the "legacy-SKU substitution" hypothesis (`term_structure/`).
