"""Rate-index path generators: 3 deterministic scenarios (Stage 1) + 3
stochastic processes (Stage 2), all producing a monthly multiplier path
where 1.0 = today's neocloud-tier rate (see rental_rate_history.csv).

Historical calibration for Stage 2 comes from only 4 period-to-period log
returns (data/rental_rate_history.csv has 5 period medians -- real
sourced data, but genuinely sparse). Every Stage 2 process calibrated here
inherits that sparsity; none of the three should be read as more
trustworthy than the data supports. That's the whole point of comparing
three of them instead of picking one -- see README "Why compare, not pick."
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


# ---- Stage 1: deterministic scenarios ----


def smooth_decline(n_months, monthly_decline_rate=0.01):
    path = [1.0]
    for _ in range(1, n_months):
        path.append(path[-1] * (1 - monthly_decline_rate))
    return path


def stair_step_with_reversal(n_months, step_down_month=18, step_down_pct=0.06, reversal_month=30, reversal_pct=0.05):
    """Mirrors the real shape in rental_rate_history.csv: flat, then a
    single-month step down (like the AWS-cut-driven move), flat, then a
    partial reversal. Magnitudes scaled to the neocloud tier's actual
    historical moves (~6% step down, ~5% partial reversal), not the much
    larger hyperscaler-tier moves."""
    path = [1.0]
    for t in range(1, n_months):
        level = path[-1]
        if t == step_down_month:
            level = level * (1 - step_down_pct)
        elif t == reversal_month:
            level = level * (1 + reversal_pct)
        path.append(level)
    return path


def aggressive_decline(n_months, monthly_decline_rate=0.025):
    path = [1.0]
    for _ in range(1, n_months):
        path.append(path[-1] * (1 - monthly_decline_rate))
    return path


# ---- Stage 2: stochastic processes ----


def gbm_paths(n_months, n_sims, monthly_returns, rng):
    mean = sum(monthly_returns) / len(monthly_returns)
    variance = sum((r - mean) ** 2 for r in monthly_returns) / (len(monthly_returns) - 1)
    vol = math.sqrt(variance)

    paths = []
    for _ in range(n_sims):
        path = [1.0]
        for _ in range(1, n_months):
            z = rng.gauss(0, 1)
            path.append(path[-1] * math.exp((mean - 0.5 * vol**2) + vol * z))
        paths.append(path)
    return paths, {"monthly_drift": mean, "monthly_vol": vol}


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


def regime_switching_paths(n_months, n_sims, monthly_returns, rng):
    """Two states, classified from the sign of each observed monthly
    return: 'decline' (negative) and 'stable_or_up' (non-negative).
    Transition probabilities and per-state drift/vol are estimated from
    only 4 observations -- explicitly the weakest-calibrated of the three
    processes here, kept deliberately for comparison, not because it's
    trusted more than the others."""
    decline = [r for r in monthly_returns if r < 0]
    stable = [r for r in monthly_returns if r >= 0]

    decline_mean = sum(decline) / len(decline) if decline else -0.01
    decline_vol = (sum((r - decline_mean) ** 2 for r in decline) / max(len(decline) - 1, 1)) ** 0.5 if len(decline) > 1 else 0.01
    stable_mean = sum(stable) / len(stable) if stable else 0.0
    stable_vol = (sum((r - stable_mean) ** 2 for r in stable) / max(len(stable) - 1, 1)) ** 0.5 if len(stable) > 1 else 0.01

    transitions = 0
    for a, b in zip(monthly_returns, monthly_returns[1:]):
        if (a < 0) != (b < 0):
            transitions += 1
    switch_prob = transitions / max(len(monthly_returns) - 1, 1)
    switch_prob = max(0.05, min(0.5, switch_prob))

    paths = []
    for _ in range(n_sims):
        state = "decline" if monthly_returns[0] < 0 else "stable_or_up"
        path = [1.0]
        for _ in range(1, n_months):
            if rng.random() < switch_prob:
                state = "stable_or_up" if state == "decline" else "decline"
            mean, vol = (decline_mean, decline_vol) if state == "decline" else (stable_mean, stable_vol)
            z = rng.gauss(0, 1)
            path.append(path[-1] * math.exp((mean - 0.5 * vol**2) + vol * z))
        paths.append(path)
    return paths, {
        "decline_monthly_drift": decline_mean,
        "decline_monthly_vol": decline_vol,
        "stable_monthly_drift": stable_mean,
        "stable_monthly_vol": stable_vol,
        "switch_prob_per_month": switch_prob,
        "n_transitions_observed": transitions,
        "n_observations": len(monthly_returns),
    }
