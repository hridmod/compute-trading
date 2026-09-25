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

Best chip: B200, 207.44 tok/s/GPU, $6.88/hr live rental.

| GPU | rental $/hr | ceiling $/hr | ratio | violation |
|---|---|---|---|---|
| H100 SXM | 3.57 | 1.62 | **2.20x** | Yes |
| H200 SXM | 4.81 | 2.29 | **2.10x** | Yes |

Hand-verified independently outside the codebase — matches exactly.

**Both legacy chips are in contango against B200**: H100 and H200 rent for
roughly 2.1-2.2x what their relative throughput vs. B200 would justify. A
buyer who could actually get B200 capacity at its quoted price would
strictly prefer it — cheaper tokens per dollar, not just faster completion.

This is consistent with the `token_parity` finding (legacy chips priced
well above what token economics alone justifies) but is a distinct signal:
that test compared hardware price to token market value; this one compares
hardware price to *other hardware*. Both pointing the same direction is
more informative than either alone — it's not just "tokens are cheap
right now," it's "legacy hardware specifically looks mispriced relative to
its own generation's best alternative."

**Most likely explanation, stated as a hypothesis, not a conclusion**: B200
is supply/allocation constrained, so its quoted spot rental price isn't
actually obtainable at the volume or reliability buyers need — legacy chips
absorb spillover demand at a premium precisely because the "efficient"
option is inaccessible, not because the market is pricing hardware
irrationally. This is testable: if true, the substitution ceiling violation
should shrink over time as B200 supply grows, which is exactly what
accumulating daily history is for.

## Open next steps

1. Track B200 `n_offers` (live inventory count) alongside price — if the
   supply-constraint hypothesis above is right, low B200 offer counts should
   correlate with wider substitution-ceiling violations on legacy chips.
2. Once real forward/futures data exists (October futures listing, or a
   reserved-vs-spot proxy), rerun this as an actual forward-curve test
   instead of the spot proxy used here — this is the natural bridge into
   `term_structure/`.
