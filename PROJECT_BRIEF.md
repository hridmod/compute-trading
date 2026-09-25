# Compute Trading — Project Brief

## What this project is

An empirical test suite for the thesis that GPU compute is commoditizing
the way oil and power did — using the pricing tools mature commodity
markets already have. The thesis comes from four source pieces (summarized
below); this repo exists to check each of their falsifiable claims against
real data, not to assume the thesis is correct.

The working style: each hypothesis gets a small, self-contained sub-project
under its own folder, with sourced/dated input data, a clear model, and an
honest README documenting what the first result actually showed (including
null results — a claim being *not yet supported* by current data is itself
useful information, not a failure).

## The source thesis, compressed

1. **A six-level commodity hierarchy applies to compute**: benchmark (L0),
   hardware grade (L1: H100/H200/B200/...), region (L2), firmness/workload
   (L3: spot/reserved, training/inference), tenor (L4), counterparty/credit
   tier (L5: hyperscaler/neocloud/cleared-vs-bilateral). Each layer has a
   direct analog already priced in crude or power markets.
2. **Two rival compute indices exist** (CME/Silicon Data — quote-based;
   ICE/Ornn/OCPI — transaction-VWAP), and whether their spread converges
   into a stable, explainable band (like WTI-Brent) or drifts unpredictably
   is the cleanest live test of whether compute "is" a commodity yet.
3. **Token prices for constant capability fall ~10x/year**, and aggregate
   compute spend keeps rising anyway because cheap tokens unlock new demand
   (agents, reasoning, video, code) faster than price falls — so far. The
   open risk: whether that demand elasticity holds through the whole cycle.
   Levered capital (neocloud debt) is implicitly short the scenario where
   it doesn't.
4. **Inference is bifurcating into prefill (compute-bound) and decode
   (memory-bandwidth-bound) phases**, increasingly served on different
   silicon. This threatens HBM-maker pricing power, makes orchestration
   (routing requests to the right chip) a new margin-control point, and
   opens room for non-Nvidia silicon in the fastest-growing segment.
5. **Financing is a maturity mismatch**: long-lived infra (15-30yr power
   assets, 20yr leases) financed against fast-decaying revenue (rental
   rates) and annual hardware turnover. Hyperscalers disagree with each
   other on useful-life assumptions (Amazon: 5yr, Meta: 5.5yr, MSFT/GOOG/
   CoreWeave: 6yr) — each dispute is a bet on the rental-decay curve's
   slope. GPU-collateralized debt (e.g. CoreWeave's $2.6B term loan,
   SOFR+550, 10.44% YTM, Ba2/BB+, 1.35x DSCR covenant) prices real distrust
   of that collateral's durability. Nvidia has stepped in as vendor
   financier/residual-value guarantor of its own product — a reflexive
   pattern flagged historically in telecom (1999) and merchant energy
   (2001), with wrong-way-risk properties since Nvidia's own product
   launches are the trigger event for repricing.
6. **There's no closed-form forward price for compute** (GPU-hours aren't
   storable, so no cash-and-carry arbitrage ties forward to spot — same
   structural problem as electricity). Three anchors bound it instead:
   - **Shutdown floor**: forward can't sustainably print below the
     marginal operator's variable cash cost (power, colo, staffing).
   - **Substitution ceiling**: no rational buyer pays more for legacy
     hours than the best future chip's cost-per-token implies.
   - **Token-parity ceiling**: rental $/hr ≤ (tokens/hr served) ×
     (market $/token) — a rational inference operator won't pay more
     than the output is worth.
   Curves should sit in backwardation by default (decay from
   substitution); **contango in a legacy-chip curve is the informative
   signal** — it means the market expects either slower substitution or
   next-gen supply disappointment. SKU spreads (H200/H100, B200/H100)
   aren't independent bets — they're tradeable proxies for the
   decode-share of aggregate demand and the generational performance gap.

## Sub-projects (planned and built)

| # | Hypothesis | Status | Folder |
|---|---|---|---|
| 1 | Token-parity ceiling holds (rental ≤ tokens/hr × $/token) | **Built, live-pulled, first result in** | `token_parity/` |
| 2 | SD vs. OCPI index spread is stable/explainable, not regime-shifting | Not started — blocked on index history depth | `index_dispersion/` (planned) |
| 3 | Legacy-SKU forward curves sit in backwardation by default; contango episodes are informative | Not started — needs forward/tenor data (proxy via reserved-vs-spot pricing pre-October futures listing) | `term_structure/` (planned) |
| 4 | H200/H100 spread tracks decode-share of demand | Not started — smaller side-study, could piggyback on `token_parity/` data | `sku_spread/` (planned) |
| 5 | Neoclouds are the most exposed book (long depreciating hardware, short falling rental rates) — build a structural credit-stress model | Not started — highest-value next build given professional background (VaR/margin analytics) | `neocloud_credit_stress/` (planned) |
| 6 | Substitution ceiling holds (legacy-chip rental ≤ best-chip cost-per-token × legacy tok/hr) — second of the three no-arbitrage forward-curve anchors from #6 | **Built, live-pulled, first result in** | `substitution_ceiling/` |

## Sub-project 1: `token_parity/` (built)

Tests the token-parity ceiling using real MLPerf throughput benchmarks
(Llama-3.1-405B, MLPerf v5.1, sourced to raw submission logs), live GPU
rental quotes (Vast.ai), and live LLM API pricing (OpenRouter) — fully
live-pulled, not static CSVs. Full detail in `token_parity/README.md`.

**Current result**: the ceiling is violated, 4-48x depending on GPU and
which of two independent pricing baskets is used (both agree on direction).
Originally scoped against Llama2-70B, which showed the ceiling as slack
(rental at 5-40% of ceiling, no violations) — replaced with Llama-3.1-405B
since Llama2-70B is a 2023-era model no longer representative of anything
deployed today. The reversal is driven almost entirely by throughput, not
the pricing assumption: a 405B dense model produces ~63x fewer tokens/sec
per GPU than the 70B model did.

**Also surfaced immediately**: pulling real benchmark data hit the
"benchmark integrity" problem head-on twice — once via secondary sources
conflating an 8-GPU system total with a per-GPU figure for the same H100
submission, once via an AI-generated web search summary silently mislabeling
GB200/GB300 results as H100/H200/B200. Both caught by tracing back to raw
MLPerf submission logs rather than trusting any paraphrase; documented in
the data notes rather than smoothed over.

## Sub-project 6: `substitution_ceiling/` (built)

Tests the second forward-curve anchor from hypothesis #6: no rational buyer
pays more for legacy hardware-hours than the best currently deployable
chip's cost-per-token implies. Reuses `token_parity/`'s verified MLPerf data
and Vast.ai puller — needs no LLM pricing basket at all, since market
$/token cancels out in a pure hardware-to-hardware comparison. Full detail
in `substitution_ceiling/README.md`.

**First result**: violated. H100 and H200 both rent at ~2.1-2.2x what their
relative throughput vs. B200 (today's best chip) would justify — legacy
hardware is in contango against the best chip, not the backwardation the
thesis expects by default. Points the same direction as `token_parity`'s
result without sharing its methodology, which is more informative than
either alone. Leading hypothesis, not yet confirmed: B200 is
supply/allocation-constrained, so legacy chips absorb spillover demand at a
premium — testable as more history accumulates. Currently a spot-price
proxy for what the thesis actually describes as a forward-curve test; real
forward data (see `term_structure/` below) would let this be tested properly.

## What's next (in rough priority order)

1. **Automate the data layer.** `token_parity/src/io.py` currently reads
   hand-maintained CSVs. Replace with a scheduled puller (provider rate
   cards, an OpenRouter/Artificial Analysis-style pricing endpoint) so the
   ceiling test can run on a cadence and the rental/ceiling ratio can be
   tracked as a time series, not a single snapshot.
2. **Segment by workload type**, not just chip — the token-parity ceiling
   should bind tightest for pure-inference/decode-heavy deployments and
   be nearly irrelevant for training-heavy rentals. Proxy this by
   splitting rental quotes by provider type (serverless API host vs. raw
   GPU-hour marketplace).
3. **Build `neocloud_credit_stress/`** — the highest-value next project
   given prior VaR/margin-analytics background. Mark GPU collateral to a
   modeled rental-decay curve (feed off `token_parity` outputs plus the
   non-monotonic 2026 pattern from the source material — H100 spot fell
   from $7/hr to a $2-4 band, then partially reversed), project debt
   service against real covenant structures (CoreWeave's 1.35x DSCR is
   the template), and stress-test under smooth-decline vs. actual
   stair-step/reversal decay assumptions.
4. **Build `index_dispersion/`** once SD (CME/Silicon Data) and OCPI
   (ICE/Ornn) have enough historical depth — regress the spread against
   the four legs the source dashboard decomposed (quote/print
   fragmentation, tier-mix delta, settlement-window mismatch, regional-
   weight delta) and test mean-reversion/stability, i.e. a cointegration-
   style test, same spirit as WTI-Brent basis modeling.
5. **Build `term_structure/`** once real forward/tenor data exists
   (October futures listing, or proxied now from reserved-vs-spot rate
   differentials across providers) — fit a simple curve-shape model
   (level/slope/curvature, Nelson-Siegel-style) and test whether curve
   shape predicts subsequent capex announcements or hyperscaler earnings
   revisions.

## Working conventions for this repo

- Every data file carries `source` and `snapshot_date` columns — no
  unsourced numbers.
- Every sub-project gets its own README stating the hypothesis, the model,
  the first result (including nulls), and open next steps — mirror the
  structure of `token_parity/README.md`.
- Keep sub-projects independent and runnable on their own
  (`pip install -r requirements.txt && python analysis/run_analysis.py`)
  rather than building one large shared framework prematurely — merge
  shared code (e.g. a common `io.py` pattern) only once 2-3 sub-projects
  show the same duplicated need.
- Flag data disagreements across sources explicitly in the CSVs and READMEs
  rather than silently picking one number — benchmark/quote heterogeneity
  is itself evidence relevant to the commoditization thesis (see the
  "benchmark integrity" risk in the source material), not noise to clean up.
