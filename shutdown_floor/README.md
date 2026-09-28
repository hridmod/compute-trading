# shutdown_floor

Tests the third and last forward-curve anchor from `PROJECT_BRIEF.md` #6:
the **shutdown floor**.

> The forward can't sustainably print below the marginal operator's
> variable cash cost (power, colo, staffing). Below it, capacity withdraws
> rather than sells. Identical to the retirement condition on a power plant.

## Model

```
floor_usd_per_hr = (tdp_watts / 1000) * PUE * electricity_usd_per_kwh
ratio            = rental_usd_per_hr / floor_usd_per_hr   # < 1.0 = violation
```

PUE (power usage effectiveness) scales the chip's own power draw up to
total facility power draw — it's the standard datacenter-industry factor
for cooling/electrical overhead, and skipping it would understate the real
cost floor.

Two scenarios, same "pick the toughest test" convention as the other two
sub-projects:

| Scenario | Electricity | PUE | Why |
|---|---|---|---|
| `toughest` | Virginia, $0.0899/kWh | 1.58 (per-site average) | Highest plausible cost — most likely to surface a violation if one exists |
| `most_efficient` | Texas, $0.0612/kWh | 1.47 (capacity-weighted) | Most realistic for large hyperscale-class fleets — least likely to show a violation |

## Data — all three legs are real, sourced, and independently verified

| File | What | Source |
|---|---|---|
| `data/gpu_power_draw.csv` | H100/H200/B200 TDP (watts) | NVIDIA's own spec pages and developer blog |
| `data/electricity_prices.csv` | Industrial $/kWh, VA / TX / US average | EIA Form 861, 2024 annual average |
| `data/pue_assumptions.csv` | Per-site and capacity-weighted PUE | Uptime Institute Global Data Center Survey 2024 |
| `data/gpu_rental.csv` | Live rental price | Vast.ai public API (same puller as the other two sub-projects) |

**Why static, not live-pulled** (for power/electricity/PUE): unlike GPU
rental spot prices, which move within minutes, industrial electricity
rates and datacenter PUE are reported annually/periodically — there's
nothing to poll on a schedule. EIA's live API needs a registered account
key (couldn't get one without creating an account on your behalf, so
skipped it); their publicly downloadable Form 861 tables don't have that
restriction and are the same underlying data.

**Region choice**: Virginia and Texas are, respectively, the #1 and #2
US states by datacenter count (663 and 405, per a Jan 2026 American Edge
Project study, together 26% of all US datacenters) — the two most
representative real anchors for where GPU rental supply actually sits,
rather than an arbitrary pick.

## What's deliberately excluded: colo lease cost and staffing

The thesis names power, colo, *and* staffing as components of variable
cash cost. This test only prices power (via TDP × PUE × electricity rate).
Colo lease and staffing are real costs, but neither has a defensible public
per-GPU-hour figure the way power does — inventing one would violate this
project's "no unsourced numbers" rule.

**Consequence**: this floor is a *lower bound*, not the true floor. The
real shutdown floor is at least this high, plausibly somewhat higher.
That biases the test toward *not* finding a violation — so a "violated"
result here would be a strong signal, but a "not violated" result doesn't
fully rule one out once real colo/staffing costs are added. Flagged, not
glossed over.

## Result (2026-09-28 live pull)

| Scenario | GPU | rental $/hr | floor $/hr | ratio | violation |
|---|---|---|---|---|---|
| toughest (VA, high PUE) | H100 SXM | 3.14 | 0.0994 | **31.6x** | No |
| toughest | H200 SXM | 4.18 | 0.0994 | **42.0x** | No |
| toughest | B200 | 7.51 | 0.1420 | **52.9x** | No |
| most_efficient (TX, low PUE) | H100 SXM | 3.14 | 0.0630 | **49.8x** | No |
| most_efficient | H200 SXM | 4.18 | 0.0630 | **66.4x** | No |
| most_efficient | B200 | 7.51 | 0.0900 | **83.5x** | No |

Hand-verified independently outside the codebase — matches exactly, both
scenarios.

**Not violated, and not close** — rental prices sit 32-83x above the
shutdown floor even under the toughest (highest-cost) assumption. Expected:
nobody's forcing a shutdown decision at these prices. But the real value of
this result is in what it does to the *other two* findings, not on its own.

## Putting all three anchors together

| Anchor | Result | What it means |
|---|---|---|
| Token-parity ceiling | Violated 4-48x | Rental is priced *above* what token resale value justifies |
| Substitution ceiling | Violated 1.6-2.2x | Legacy chips priced *above* what relative hardware efficiency justifies |
| Shutdown floor | Slack 32-83x | Rental is priced *far above* the minimum needed to keep operating |

Current GPU rental pricing sits in a wide band above every anchor tested —
nowhere near the floor, and well above both ceilings. None of the three
disciplines tested here is what's setting the marginal price right now.
That's not a null result across the board; it's a specific, positive
finding: current pricing has a lot of room to fall before any of these
constraints would bind, and whatever *is* setting price (scarcity,
allocation, demand exceeding either chip generation's available supply —
see `substitution_ceiling`'s supply-signal finding) is doing so well inside
all three boundaries, not at the edge of any of them.

## Running it

```
pip install -r requirements.txt
python analysis/run_analysis.py          # pulls live rental data, runs both scenarios, appends history
python analysis/run_analysis.py --no-pull  # reuse cached data/gpu_rental.csv, skip the live pull
python analysis/backtest.py              # report the ratio across all accumulated history
```

`.github/workflows/daily_snapshot.yml` runs this alongside the other two
sub-projects daily.

## Open next steps

1. Find a defensible per-GPU-hour colo lease figure (industry $/kW-month
   colocation pricing reports) to turn the lower bound into a tighter
   estimate of the true floor.
2. Since the floor is this slack, it's very unlikely to ever bind at
   current price levels — worth checking in occasionally via the
   accumulating history rather than actively monitoring for it.
3. This closes out all three anchors from thesis #6. Natural next step per
   `PROJECT_BRIEF.md`'s roadmap is `neocloud_credit_stress/` — feeds off
   all three of these results (a neocloud's debt service assumes rental
   revenue; these findings bound how much room that revenue has to fall
   before hitting each constraint).
