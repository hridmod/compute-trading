# neocloud_credit_stress

Tests hypothesis #5 from `PROJECT_BRIEF.md`: neoclouds are the most exposed
book in the compute trade — long depreciating hardware, short rapidly-moving
rental rates, financed with real debt and a real covenant. A structural
project-finance credit model, not a vague "stress test": track a DSCR
covenant and a collateral LTV ratio over time under a stochastic process
for the one variable that actually moves — the rental rate the fleet earns.

## The real facility this is built on

CoreWeave's DDTL V-V facility, closed late July 2026 (all figures verified
this session, sourced per-field in `data/debt_terms.csv`):

- **$2.6B**, SOFR+550bps (repriced wider from an initial 425-450bps guide),
  all-in YTM 10.44%
- **1.35x DSCR maintenance covenant** — tested continuously, not just at
  maturity
- **$112.5M minimum liquidity covenant** — a second, independent trigger,
  not modeled here (no cash-balance data available — see Open next steps)
- Full amortization to Sept 2031, no balloon — modeled as straight-line
  principal over ~61 months (the exact schedule shape isn't disclosed)
- Ba2 (Moody's) / BB+ (Fitch)
- Tested at the DDTL V-V borrower/SPV level, against *this tranche's*
  specific customer contracts — not CoreWeave Inc.'s whole-company financials

## Why per-capex-dollar, not per-GPU-count

The press release doesn't disclose how many GPUs, or what mix, the $2.6B
actually finances. Rather than guess a fleet size (and inherit that guess's
error into every downstream number), the model runs entirely in
dollar-of-capex terms: revenue, opex, and implied fleet-hours are all
derived from real disclosed company-wide ratios, scaled to the $2.6B
facility size. See `src/model.py::calibrate()`.

## Calibration — and a real finding it surfaced immediately

Baseline revenue is estimated by applying CoreWeave's actual FY2025
whole-company revenue-to-total-debt ratio (`$5.13B / $21.4B ≈ 0.24`) to the
$2.6B facility size, with opex sized to match the real ~60% adjusted
EBITDA margin. The power/cooling slice of that opex uses `shutdown_floor`'s
own verified H100 floor ($0.063/hr) — a real link between two sub-projects
in this repo, not a fresh assumption (see `data/opex_calibration.csv`).

**Running that calibration through the waterfall with *zero* rate decay
applied gives month-1 DSCR = 0.49x — already well below the 1.35x covenant,
before any stress at all.** Hand-verified independently outside the
codebase. This tranche would need to generate **2.04x** the whole-company
average revenue-per-debt-dollar to clear covenant today. Two readings:

1. The whole-company blended ratio genuinely doesn't represent this
   specific tranche — it's backed by newer, individually-underwritten
   contracts (per the facility's own disclosure), not a cross-section of
   CoreWeave's full, more-seasoned book. Entirely plausible, and 2.0x isn't
   an absurd premium for new, better-monetized capacity.
2. Or this tranche really is underwater on day one, and the 100-125bps
   spread blowout plus the first DSCR covenant CoreWeave's lenders have
   demanded "in over a decade" (per the techtimes coverage) is the market
   pricing exactly that.

This data can't distinguish the two. Flagged as the central open question,
not resolved — see `analysis/run_scenarios.py` output for the exact
figures. **All scenario and Monte Carlo results below use a *second*
calibration, scaled so month-1 DSCR sits exactly at 1.35x with zero decay**
— i.e., assuming reading (1). This isolates rate-decay risk (the thing
this sub-project actually set out to test) from the baseline-tightness
question above, which is a separate, unresolved issue.

## Historical calibration for the decay processes

`data/rental_rate_history.csv` — Silicon Data's published neocloud-tier
history (notably: this is the literal index CME lists GPU futures against,
launching Oct 5, 2026 — not an arbitrary third-party proxy). Only **5
period medians, 4 derived monthly-equivalent log-returns.** Genuinely
sparse. Every Stage 2 process below inherits that sparsity.

## Stage 1: deterministic scenarios

```
python analysis/run_scenarios.py
```

Three hand-specified paths (smooth decline, a stair-step-with-reversal
shaped like the real history's AWS-cut-and-partial-recovery pattern, and
an aggressive decline) run through the covenant-clearing calibration.

| Scenario | min DSCR | breach? | first breach | max LTV |
|---|---|---|---|---|
| smooth_decline (1%/mo) | 0.86 | Yes | month 2 | 0.998 |
| stair_step_with_reversal | 1.35 | **No** | — | 0.998 |
| aggressive_decline (2.5%/mo) | 0.06 | Yes | month 2 | 0.998 |

**The stair-step scenario not breaching is a real, hand-verified result,
not a bug**: debt service *shrinks* every month as the loan amortizes
(interest on a declining balance), so DSCR has a natural cushion that
builds over time even at a flat rate. A modest, realistic-magnitude shock
(6%, matching the real historical neocloud-tier move) arrives too late
(month 18) to overcome the cushion already built up by then. A *sustained*
decline (smooth or aggressive) erodes DSCR faster than amortization can
rebuild it, and breaches almost immediately. **Shape and timing of a rate
shock matters as much as its magnitude** — a genuine, specific finding,
not something assumed going in.

## Stage 2: Monte Carlo (GBM vs. block-bootstrap vs. regime-switching)

```
python analysis/run_monte_carlo.py [n_sims]   # default 2000, seed fixed for reproducibility
```

All three calibrated off the same 4 sparse observations.

| Process | P(breach) | median time-to-breach | min-DSCR CVaR (worst 10%) |
|---|---|---|---|
| GBM | 46.1% | 2mo | 1.26 |
| Block bootstrap | 25.1% | 2mo | 1.32 |
| Regime-switching | **86.6%** | 2mo | 0.97 |

**61.5 percentage point spread.** This is the comparison this sub-project
was actually built to run, and the spread is the headline finding, not any
single number in the table. Regime-switching's result is the least
trustworthy of the three — its switch probability (50%/month) is estimated
from just **2 observed transitions in 4 data points**, which is exactly
the instability concern raised before any of this was built (see this
sub-project's design conversation: comparing three processes instead of
picking regime-switching alone was the direct response to that concern,
and the result vindicates it — regime-switching's extremity here looks
like small-sample noise, not a sharper signal).

**Read this as**: breach risk is real and directionally consistent across
all three methods (even the most conservative, block-bootstrap, puts it at
1-in-4), but the *exact* probability is not something 4 historical data
points can pin down. That uncertainty is itself the finding.

## What this model doesn't capture

- **LTV never responds to the rate-decay simulation at all** — checked
  directly: a flat path and a 90%-crash path produce an identical max LTV
  (0.998) to 4 decimal places. Collateral is modeled via CoreWeave's own
  straight-line, no-salvage book-depreciation policy; the loan amortizes on
  a fixed schedule. Neither is tied to rental-rate performance in this
  model. The original design conversation for this sub-project flagged that
  book depreciation and rental-rate-implied *economic* value could diverge
  — that divergence is real, but marking collateral to a rate-linked
  economic value (rather than book value) wasn't actually implemented.
  Real gap, not a finding — see Open next steps.
- **The $112.5M minimum liquidity covenant** is a second, independent
  breach trigger not modeled at all (no cash-balance data available).
- **Microsoft is ~67% of CoreWeave's FY2025 revenue** (real, disclosed,
  `data/company_financials.csv`) — correlated counterparty risk, entirely
  separate from rental-rate decay, not modeled here.
- **SOFR is held flat** at 3.90% for the full 61-month horizon. Real rate
  path risk (compounding with spread risk) isn't simulated.
- **Utilization is implicitly assumed constant** — revenue scales with
  rate_index alone, not with any modeled drop in fleet utilization, which
  would compound a rate decline in reality.

## Two bugs caught during the build, worth recording

1. **Floating-point breach tolerance.** The covenant-clearing calibration
   is supposed to put month-1 DSCR at *exactly* 1.35x with zero decay.
   Checked the raw float and it came out `1.34999999999999986677` against a
   covenant stored as `1.35000000000000008882` — a ~2e-16 gap from
   floating-point accumulation through the calibration chain, not an
   economic result. A bare `<` comparison flagged every "exactly at
   covenant" case as a breach. Fixed with an explicit tolerance
   (`model.BREACH_TOLERANCE`), documented in `run_waterfall()`'s docstring
   so it isn't silently "fixed" again by someone who doesn't know why it's
   there.
2. **Opex/revenue scaling mismatch.** An earlier version of
   `scale_to_covenant_clearing()` scaled both opex and revenue by the
   required efficiency multiple, but `required_efficiency_multiple()`
   computed that multiple against *unscaled* opex — an inconsistency that
   silently produced month-1 DSCR of 1.01x instead of the intended 1.35x.
   Caught by hand-verifying the calibration output before trusting it, same
   standard applied everywhere else in this repo. Fixed by scaling revenue
   only (see the docstring on `scale_to_covenant_clearing()` for the
   economic reasoning on why that's the more defensible choice, not just
   the one that makes the arithmetic close).

## Running it

```
pip install -r requirements.txt
python analysis/run_scenarios.py       # Stage 1: deterministic, fast
python analysis/run_monte_carlo.py     # Stage 2: stochastic comparison, ~2000 sims/process
```

No live data pulls in this sub-project — every input is either a static
sourced fact (debt terms, useful life, company financials, historical
rental rates) or a copied, cited value from `shutdown_floor`'s own verified
output. Nothing here changes day to day the way the other three
sub-projects' live rental/pricing pulls do.

## Open next steps

1. Model the $112.5M minimum liquidity covenant as a second breach
   condition, once a defensible cash-balance assumption exists.
2. Mark collateral to a rate-linked economic value (not just book
   depreciation) so LTV actually responds to the Monte Carlo simulation —
   the single biggest gap between what this sub-project set out to model
   and what it actually models right now.
3. Resolve the baseline-tightness open question (2.04x) with better data
   if CoreWeave or the arranging banks ever disclose tranche-specific
   contract terms rather than whole-company financials.
4. Once CME's Silicon Data futures are live (Oct 5, 2026), replace the
   historical-calibration step with real forward-implied rate expectations
   for at least the near-dated months — directly upgrades Stage 2's weakest
   link (4 historical observations) with actual market-implied data.
