"""Substitution ceiling model.

Hypothesis (thesis claim, see PROJECT_BRIEF.md #6): no rational buyer pays
more for legacy hardware-hours than the best currently deployable chip's
cost-per-token implies. If a buyer could get cheaper tokens by switching to
the best chip, the best chip's cost-per-token caps what any legacy SKU can
rationally rent for:

    cost_per_token(chip) = rental_usd_per_hr(chip) / (tokens_per_sec(chip) * 3600)

    ceiling_usd_per_hr(legacy) = cost_per_token(best_chip) * tokens_per_sec(legacy) * 3600
                                = rental_usd_per_hr(best_chip) * tokens_per_sec(legacy) / tokens_per_sec(best_chip)

    ratio = actual_rental_usd_per_hr(legacy) / ceiling_usd_per_hr(legacy)

ratio > 1.0 is a ceiling violation: the legacy chip rents for more than its
relative throughput vs. the best chip would justify -- a rational buyer
should switch to the best chip instead. Per the source thesis: curves should
sit in backwardation by default (legacy hours cheaper, decaying toward this
ceiling); a legacy SKU printing *above* it is the informative signal --
slower expected substitution, best-chip scarcity, or demand the best chip
can't currently absorb (capacity constraints, allocation, queue time).

Unlike token_parity, this doesn't need any LLM token-pricing proxy at all --
it's a pure hardware-to-hardware comparison, so market $/token cancels out.
Uses the *offline* MLPerf scenario (max throughput) for the same reason as
token_parity: the most generous, hardest-to-violate ceiling.
"""

SECONDS_PER_HOUR = 3600


def offline_tokens_per_sec_per_gpu(mlperf_rows, gpu):
    for r in mlperf_rows:
        if r["gpu"] == gpu and r["scenario"] == "offline" and r["normalization"] == "per_gpu":
            return float(r["tokens_per_sec"])
    return None


def best_chip(mlperf_rows, rental_rows):
    """The chip with the highest offline tok/s among those with a live rental quote."""
    candidates = []
    for rental in rental_rows:
        gpu = rental["gpu"]
        tps = offline_tokens_per_sec_per_gpu(mlperf_rows, gpu)
        if tps is not None:
            candidates.append((gpu, tps, float(rental["dph_median"])))
    if not candidates:
        return None
    return max(candidates, key=lambda c: c[1])


def compute_substitution_test(mlperf_rows, rental_rows):
    """Return one result dict per legacy GPU (every GPU except the best chip)."""
    best = best_chip(mlperf_rows, rental_rows)
    if best is None:
        raise ValueError("no GPU has both a benchmark and a rental quote")
    best_gpu, best_tps, best_rental = best

    results = []
    for rental in rental_rows:
        gpu = rental["gpu"]
        if gpu == best_gpu:
            continue
        tps = offline_tokens_per_sec_per_gpu(mlperf_rows, gpu)
        if tps is None:
            continue
        ceiling_usd_per_hr = best_rental * tps / best_tps
        rental_usd_per_hr = float(rental["dph_median"])
        results.append(
            {
                "gpu": gpu,
                "best_chip": best_gpu,
                "offline_tokens_per_sec": tps,
                "best_chip_tokens_per_sec": best_tps,
                "best_chip_rental_usd_per_hr": best_rental,
                "ceiling_usd_per_hr": round(ceiling_usd_per_hr, 4),
                "rental_usd_per_hr": rental_usd_per_hr,
                "ratio": round(rental_usd_per_hr / ceiling_usd_per_hr, 4),
                "violation": rental_usd_per_hr > ceiling_usd_per_hr,
            }
        )
    return results
