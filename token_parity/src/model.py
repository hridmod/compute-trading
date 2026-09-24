"""Token-parity ceiling model.

Hypothesis (thesis claim, see PROJECT_BRIEF.md #6): a rational inference
operator won't pay more per GPU-hour to rent hardware than the tokens that
hardware can serve are worth on the open market. So:

    ceiling_usd_per_hr = tokens_per_sec (offline, per-GPU) * 3600
                         * market_usd_per_completion_token

    ratio = actual_rental_usd_per_hr / ceiling_usd_per_hr

ratio > 1.0 is a ceiling violation: the market is paying more for the raw
hardware-hour than the tokens it can produce are worth, i.e. something other
than token economics (scarcity, training demand, substitution premium) must
be setting the price.

We use the *offline* MLPerf scenario (max achievable throughput, not
latency-constrained) as the generous, best-case ceiling -- if rental price
still exceeds this generous ceiling, that's a strong violation signal. We use
the *median* completion price across the comparable-capability model basket
(src/pull_llm_pricing.py) as the market $/token, and *median* rental price
across live offers as the actual rental rate.
"""

SECONDS_PER_HOUR = 3600


def median(values):
    values = sorted(values)
    n = len(values)
    if n == 0:
        return None
    mid = n // 2
    return values[mid] if n % 2 else (values[mid - 1] + values[mid]) / 2


def market_usd_per_token(llm_pricing_rows):
    completion_prices = [
        float(r["completion_usd_per_token"])
        for r in llm_pricing_rows
        if r.get("completion_usd_per_token") not in (None, "", "None")
    ]
    return median(completion_prices)


def offline_tokens_per_sec_per_gpu(mlperf_rows, gpu):
    for r in mlperf_rows:
        if r["gpu"] == gpu and r["scenario"] == "offline" and r["normalization"] == "per_gpu":
            return float(r["tokens_per_sec"])
    return None


def compute_ceiling_test(mlperf_rows, rental_rows, llm_pricing_rows):
    """Return one result dict per GPU that has both a benchmark and a rental quote."""
    market_rate = market_usd_per_token(llm_pricing_rows)
    if market_rate is None:
        raise ValueError("no usable completion pricing in llm_pricing_rows")

    results = []
    for rental in rental_rows:
        gpu = rental["gpu"]
        tps = offline_tokens_per_sec_per_gpu(mlperf_rows, gpu)
        if tps is None:
            continue
        ceiling_usd_per_hr = tps * SECONDS_PER_HOUR * market_rate
        rental_usd_per_hr = float(rental["dph_median"])
        results.append(
            {
                "gpu": gpu,
                "offline_tokens_per_sec": tps,
                "market_usd_per_token": market_rate,
                "ceiling_usd_per_hr": round(ceiling_usd_per_hr, 4),
                "rental_usd_per_hr": rental_usd_per_hr,
                "ratio": round(rental_usd_per_hr / ceiling_usd_per_hr, 4),
                "violation": rental_usd_per_hr > ceiling_usd_per_hr,
            }
        )
    return results
