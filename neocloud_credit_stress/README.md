# neocloud_credit_stress

Tests hypothesis #5 from `PROJECT_BRIEF.md`: neoclouds are the most exposed
book in the compute trade — long depreciating hardware, short rapidly-moving
rental rates, financed with real debt and a real covenant. A structural
project-finance credit model: track a DSCR covenant over time under a
stochastic process for the one variable that actually moves — the rental
rate the fleet earns.

**Deliberately narrow.** An earlier version of this compared three
deterministic scenarios and three stochastic processes on top of a
calibration patched to force a convenient starting point — six parallel
analyses, each only loosely grounded. This version does one calibration and
one stochastic process, both built to be defensible on their own, not
compared against alternatives for lack of confidence in any single one.

## The real facility this is built on

CoreWeave's DDTL V-V facility, closed late July 2026 (sourced per-field in
`data/debt_terms.csv`): **$2.6B**, SOFR+550bps (repriced wider from an
initial 425-450bps guide), all-in YTM 10.44%, **1.35x DSCR maintenance
covenant**, full amortization to Sept 2031 (~61 months, modeled
straight-line), Ba2/BB+. Tested at the DDTL V-V borrower/SPV level against
this tranche's specific customer contracts, not CoreWeave Inc.'s
whole-company financials.

## Calibration: bottom-up from hardware cost, not a backed-out ratio

The press release doesn't disclose the GPU count this facility financed.
An earlier version inferred revenue from CoreWeave's company-wide
revenue-to-debt ratio, found the result deeply breached the covenant before
any stress was applied, and patched around that with an invented
"required efficiency multiple" to force a workable starting point. That
patch is gone. This version builds up from real hardware cost instead:

```
cost_per_gpu        = avg(8-GPU H100 server cost range) / 8        = $40,625
fleet_size           = loan_amount / cost_per_gpu                   = 64,000 GPUs
fleet_hours/year     = fleet_size * 8760 * utilization               = 532.6M
baseline_revenue    = fleet_hours/year * rate_baseline (neocloud tier) = $1,864.1M/yr
baseline_opex        = baseline_revenue * (1 - EBITDA margin)         = $745.7M/yr
```

Each link in that chain is sourced in `data/fleet_calibration.csv`:
hardware cost from a public neocloud unit-economics analysis; the 95%
utilization figure from a separate source stating that debt-financed
builds backed by customer offtake contracts run "effectively 100%" utilized
(capacity sold before the GPU is racked) — matching CoreWeave's own
disclosure that this facility is backed by specific customer contracts.
Used 95%, not literal 100%, as a conservative haircut. EBITDA margin (60%)
and the power/cooling opex component ($0.063/hr, from `shutdown_floor`'s
own verified output) are the same real, sourced figures as before.

**Result: month-1 DSCR = 1.48x — comfortably above the 1.35x covenant,
with no scaling or patching required.** Hand-verified independently
outside the codebase, matches exactly. One assumption chain, each link
sourced, instead of two stacked ones.

## Sanity check: one realistic shock

```
python analysis/run_scenarios.py
```

A step-down-then-partial-reversal path (6% down at month 18, 5% back at
month 30 — scaled to the real historical neocloud-tier move, not invented)
doesn't breach either: min DSCR 1.47x. Debt service shrinks every month as
the loan amortizes, building a natural cushion that absorbs a shock of this
realistic size.

## Monte Carlo: block bootstrap only

```
python analysis/run_monte_carlo.py [n_sims]   # default 2000, seed fixed for reproducibility
```

Simulates many future rate paths by resampling real historical
month-over-month moves (not assuming a distribution). Calibrated off the
same 4 sparse historical observations as before — genuinely thin, flagged
clearly in the script's own output.

**Result: 0 breaches in 2000 simulated 61-month paths** (confirmed again
at 20,000). min-DSCR averages 1.47x across simulations; even the worst 10%
of paths average 1.44x — still above covenant.

**This does not mean the loan is safe, and the script says so explicitly.**
Block bootstrap can only ever recombine the moves it was given — it
structurally cannot generate a shock larger than the worst single historical
observation (-2.09%/month). Checked the genuine ceiling on how bad this
method could ever show: repeating that single worst month for all 61
months straight (an astronomically unlikely draw, but the real limit of
what bootstrap can produce) gives DSCR of **-0.42x — a severe breach.**
So the honest reading is: **no risk shows up beyond what 4 historical data
points can describe.** A real shock outside that envelope — a demand
collapse, a chip oversupply event, anything genuinely novel — isn't
represented in this model at all, by construction, no matter how many
times the simulation is run.

## What this still doesn't capture

- **LTV isn't modeled as responsive to rate decay** — collateral uses
  CoreWeave's straight-line book-depreciation policy, independent of
  rental-rate performance. A real gap between book and economic collateral
  value, not implemented here.
- **The $112.5M minimum liquidity covenant** — a second, independent
  breach trigger, not modeled (no cash-balance data available).
- **Microsoft is ~67% of CoreWeave's FY2025 revenue** (real, disclosed) —
  correlated counterparty risk, separate from rate decay, not modeled.
- **SOFR held flat** at 3.90% for the full horizon — real rate-path risk
  isn't simulated.
- **GPU mix assumed to be H100-class** for the hardware-cost calibration —
  the facility's actual mix (could include H200/B200, which cost more per
  unit) isn't disclosed.

## Running it

```
pip install -r requirements.txt
python analysis/run_scenarios.py       # calibration + one realistic sanity check
python analysis/run_monte_carlo.py     # block-bootstrap simulation + worst-case structural check
```

No live data pulls — every input is a static sourced fact or a copied,
cited value from `shutdown_floor`'s own output.

## Open next steps

1. The bootstrap's structural ceiling (can't exceed the worst historical
   observation) is the real limitation now, not calibration shakiness.
   Worth sourcing a genuinely tail scenario by hand (not from this
   historical window) specifically to stress-test beyond what 4 data
   points can describe.
2. Model the $112.5M liquidity covenant as a second breach condition.
3. Mark collateral to a rate-linked economic value so LTV responds to the
   simulation, not just book depreciation.
4. Once CME's Silicon Data futures are live (Oct 5, 2026), real
   forward-implied rate expectations could replace the thin 4-point
   historical calibration entirely.
