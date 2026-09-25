# substitution_ceiling

Tests the second forward-curve anchor from `PROJECT_BRIEF.md` #6: the
**substitution ceiling**.

> No rational buyer pays more for legacy hardware-hours than the best
> currently deployable chip's cost-per-token implies. If a buyer could get
> cheaper tokens by switching to the best chip, the best chip's
> cost-per-token caps what any legacy SKU can rationally rent for.

Curves should sit in backwardation by default (legacy hours discounted
below this ceiling, decaying toward it). A legacy SKU printing *above* it —
contango — is the informative signal: the market expects slower
substitution, or the best chip is supply-constrained/allocated such that
buyers can't actually get it at its quoted price.

## Model

```
cost_per_token(chip)      = rental_usd_per_hr(chip) / (tokens_per_sec(chip) * 3600)
ceiling_usd_per_hr(legacy) = rental_usd_per_hr(best_chip) * tokens_per_sec(legacy) / tokens_per_sec(best_chip)
ratio                      = rental_usd_per_hr(legacy) / ceiling_usd_per_hr(legacy)   # > 1.0 = violation
```

"Best chip" = whichever GPU has the highest offline MLPerf throughput among
those with a live rental quote that day — not hardcoded to B200. If B200
rental data is unavailable on a given pull, the ceiling shifts to whatever
the fastest-with-a-live-quote chip is. Worth knowing if a result looks like
it moved for no reason — it may be a best-chip change, not a price change.

**Cleaner than `token_parity` in one respect**: this needs no LLM
token-pricing basket at all. It's a pure hardware-to-hardware comparison —
market $/token cancels out algebraically, so there's no proxy-selection
assumption to defend.

## Data

Reuses `token_parity`'s already-verified MLPerf benchmark data (same file,
copied — not symlinked, per this repo's "keep sub-projects independent"
convention) and the identical Vast.ai rental puller. This is the second
sub-project needing both, which is this repo's own stated threshold for
considering shared code (see `PROJECT_BRIEF.md`'s working conventions) —
flagging it here rather than silently extracting it, since that's a real
design decision, not a trivial one.

All MLPerf sourcing/verification detail (raw MLPerf v5.1 logs, cross-checked
against two independent submitters, the H100-is-a-16-GPU-not-8-GPU caveat)
is identical to `token_parity/README.md` — see that file rather than
duplicating the explanation here.

## Important limitation: this is a spot proxy, not a forward test

The actual thesis claim is about *forward* curves — whether a legacy SKU's
priced-in expectation of future substitution is realistic. This test uses
today's live spot rental prices for both the legacy chip and the best chip,
which tests something narrower: is legacy hardware priced efficiently
*right now* relative to the best chip *right now*. That's a reasonable spot
proxy (same one `term_structure/` is scoped to use once real forward data
exists — see `PROJECT_BRIEF.md`), but it is not yet the forward-curve test
the thesis actually describes. Flagged, not glossed over.

Also assumed: the best chip's live rental price is itself an efficient,
uninflated reference point. If B200 carries its own scarcity premium, the
ceiling computed here is inflated too, which would understate how large the
legacy-chip violation really is — this test can't detect that from inside
itself.

## Running it

```
pip install -r requirements.txt
python analysis/run_analysis.py          # pulls live data, runs the test, appends a history snapshot
python analysis/run_analysis.py --no-pull  # reuse cached data/*.csv, skip the live pull
python analysis/backtest.py              # report the ratio across all accumulated history
```

`.github/workflows/daily_snapshot.yml` runs this alongside `token_parity`
daily, committing both sub-projects' updated `data/` back to the repo.

## Result (2026-09-25 live pull)

Best chip: B200, 207.44 tok/s/GPU. Two pulls made minutes apart while
building this (B200 only had 2 live offers, so its price moved between
them — itself a data point, see Supply signal below):

| Pull | GPU | rental $/hr | ceiling $/hr | ratio | violation |
|---|---|---|---|---|---|
| 1 (B200 @ $6.88/hr) | H100 SXM | 3.57 | 1.62 | **2.20x** | Yes |
| 1 | H200 SXM | 4.81 | 2.29 | **2.10x** | Yes |
| 2 (B200 @ $9.13/hr) | H100 SXM | 3.44 | 2.15 | **1.60x** | Yes |
| 2 | H200 SXM | 4.90 | 3.04 | **1.61x** | Yes |

Hand-verified independently outside the codebase both times — matches
exactly. Ratio magnitude moved with B200's price (expected, mechanical —
see the model above), but the conclusion didn't: **every pull today, both
legacy chips are in contango against B200**, never the reverse.

A buyer who could actually get B200 capacity at its quoted price would
strictly prefer it — cheaper tokens per dollar, not just faster completion.
This is consistent with the `token_parity` finding (legacy chips priced
well above what token economics alone justifies) but is a distinct signal
via a completely different method: that test compared hardware price to
token market value; this one compares hardware price to *other hardware*.

## Supply signal: is B200 actually supply-constrained?

The leading hypothesis for the violation above is that B200 is
supply/allocation-constrained — its quoted spot price isn't really
obtainable at the volume buyers need, so demand spills into legacy chips at
a premium. Two things were checked specifically to test this, not just
asserted:

**Utilization — tried, dead end.** Queried Vast.ai without its `rentable`
filter to see if currently-occupied machines would surface. Every offer
returned had `rented: False` regardless of `rentable` value — this endpoint
only ever lists not-currently-rented capacity, so there's no way to compute
a true rented/total utilization ratio from it. Worth knowing this doesn't
work rather than silently building on it.

**Cross-market stock check — a real, independent signal.** RunPod exposes a
public `stockStatus` field with no auth required. Same-day check:

| GPU | RunPod stock | RunPod price |
|---|---|---|
| B200 | **no live-priced offer at all** | — |
| H100 SXM | Low | $2.69/hr |
| H200 SXM | Low | $3.59/hr |

Every current-gen Hopper chip (H100, H200) shows constrained-but-available
stock on a *second, independent* marketplace; B200 shows nothing at all.
Re-queried twice to confirm it wasn't a transient blip — same result both
times. This corroborates the substitution-ceiling violation from a
completely different angle than either ceiling test.

**Caveat, stated explicitly**: `stockStatus: null` can't distinguish two
different stories from this data alone — (a) all installed B200 capacity is
currently rented (real excess demand), vs. (b) RunPod has catalogued B200
but hasn't deployed it yet (a rollout-timing story). Both are consistent
with "buyers can't reliably get B200 right now," which is what this test
needs, but they imply different things about *why*, and this data can't
tell them apart.

Now tracked automatically: `data/history/supply_signals.csv` logs Vast.ai
`n_offers` and RunPod `stockStatus`/price per GPU on every run, alongside
the substitution ceiling snapshot.

## Important limitation: this is a spot proxy, not a forward test

The actual thesis claim is about *forward* curves — whether a legacy SKU's
priced-in expectation of future substitution is realistic. This test uses
today's live spot rental prices for both the legacy chip and the best chip,
which tests something narrower: is legacy hardware priced efficiently
*right now* relative to the best chip *right now*. That's a reasonable spot
proxy (same one `term_structure/` is scoped to use once real forward data
exists — see `PROJECT_BRIEF.md`), but it is not yet the forward-curve test
the thesis actually describes. Flagged, not glossed over.

Also assumed: the best chip's live rental price is itself an efficient,
uninflated reference point. If B200 carries its own scarcity premium — which
the supply signal above suggests it might — the ceiling computed here is
inflated too, which would understate how large the legacy-chip violation
really is. This test can't correct for that from inside itself; it can only
flag the possibility.

## Running it

```
pip install -r requirements.txt
python analysis/run_analysis.py          # pulls live data, runs the test, appends history (both files)
python analysis/run_analysis.py --no-pull  # reuse cached data/*.csv, skip the live pull
python analysis/backtest.py              # report the ratio across all accumulated history
```

`.github/workflows/daily_snapshot.yml` runs this alongside `token_parity`
daily, committing both sub-projects' updated `data/` back to the repo.

## Open next steps

1. Once enough `supply_signals.csv` history accumulates: check whether the
   substitution-ceiling ratio actually correlates with Vast.ai `n_offers` /
   RunPod stock status over time, as the supply-constraint hypothesis
   predicts — and whether RunPod's B200 stock status ever goes non-null.
2. Once real forward/futures data exists (October futures listing, or a
   reserved-vs-spot proxy), rerun this as an actual forward-curve test
   instead of the spot proxy used here — this is the natural bridge into
   `term_structure/`.
