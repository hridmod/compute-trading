"""Rate-index path generators, producing a monthly multiplier path where
1.0 = today's neocloud-tier rate (see rental_rate_history.csv).

Trimmed deliberately to one deterministic sanity-check path and one
stochastic process (block bootstrap). An earlier version compared three
deterministic scenarios and three stochastic processes (also GBM and
regime-switching) -- useful for showing that regime-switching's extreme
output was small-sample noise (only 2 observed transitions in 4 data
points), but six parallel analyses on top of a shaky calibration was more
breadth than the data could support. Block bootstrap is the one kept for
depth: it needs no invented distribution, just resamples real historical
price moves directly, which is the most defensible choice given only 4
historical observations either way.
"""
import datetime
import math


def _period_midpoint(row):
    start = datetime.date.fromisoformat(row["period_start"])
    end = datetime.date.fromisoformat(row["period_end"])
    return start + (end - start) / 2


def historical_monthly_log_returns(rental_history_rows):
    """Derive monthly-equivalent log returns from the sparse period-median
    series. Each consecutive pair of periods gives one observed return,
    scaled by the actual gap (in months) between their midpoints."""
    points = [(_period_midpoint(r), float(r["price_median_usd_per_hr"])) for r in rental_history_rows]
    points.sort(key=lambda p: p[0])

    monthly_returns = []
    for (d0, p0), (d1, p1) in zip(points, points[1:]):
        gap_months = (d1 - d0).days / 30.44
        if gap_months <= 0:
            continue
        total_log_return = math.log(p1 / p0)
        monthly_returns.append(total_log_return / gap_months)
    return monthly_returns


def stair_step_with_reversal(n_months, step_down_month=18, step_down_pct=0.06, reversal_month=30, reversal_pct=0.05):
    """Deterministic sanity check: mirrors the real shape in
    rental_rate_history.csv -- flat, a single-month step down (like the
    AWS-cut-driven move), flat, then a partial reversal. Magnitudes scaled
    to the neocloud tier's actual historical moves (~6% step down, ~5%
    partial reversal), not the much larger hyperscaler-tier moves."""
    path = [1.0]
    for t in range(1, n_months):
        level = path[-1]
        if t == step_down_month:
            level = level * (1 - step_down_pct)
        elif t == reversal_month:
            level = level * (1 + reversal_pct)
        path.append(level)
    return path


def block_bootstrap_paths(n_months, n_sims, monthly_returns, rng, block_size=3):
    n_obs = len(monthly_returns)
    paths = []
    for _ in range(n_sims):
        path = [1.0]
        while len(path) < n_months:
            start = rng.randrange(0, n_obs)
            block = [monthly_returns[(start + i) % n_obs] for i in range(block_size)]
            for r in block:
                if len(path) >= n_months:
                    break
                path.append(path[-1] * math.exp(r))
        paths.append(path[:n_months])
    return paths, {"block_size": block_size, "n_source_obs": n_obs}
