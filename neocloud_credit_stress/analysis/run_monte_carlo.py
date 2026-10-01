"""Stage 2: Monte Carlo comparison of three stochastic rate-decay processes
(GBM, block-bootstrap, regime-switching), all calibrated off the same
sparse 4-observation historical series (data/rental_rate_history.csv).

None of the three should be read as more trustworthy than the data
supports -- that's the point of comparing them instead of picking one.
Where they agree, that's a more robust conclusion than any single process
alone. Where they diverge, the divergence itself is the finding: it means
covenant-breach risk is sensitive to a modeling choice this little data
can't actually settle.

Usage: python analysis/run_monte_carlo.py [n_sims]
"""
import random
import statistics
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src import decay_processes as decay  # noqa: E402
from src import io  # noqa: E402
from src import model  # noqa: E402

SEED = 20261001  # fixed for reproducibility -- same seed always reproduces this result exactly
DEFAULT_N_SIMS = 2000
CVAR_TAIL_FRACTION = 0.10


def cvar(values, tail_fraction):
    """Expected value of the worst tail_fraction of values (lower = worse here, so CVaR of DSCR = average of the worst/lowest DSCR outcomes)."""
    ordered = sorted(values)
    n_tail = max(1, int(len(ordered) * tail_fraction))
    return sum(ordered[:n_tail]) / n_tail


def simulate(process_name, paths, calibration):
    breach_months = []
    min_dscrs = []
    n_breach = 0
    for path in paths:
        rows = model.run_waterfall(calibration, path)
        summary = model.summarize_run(rows, calibration["dscr_covenant"])
        min_dscrs.append(summary["min_dscr"])
        if summary["any_breach"]:
            n_breach += 1
            breach_months.append(summary["first_breach_month"])

    n = len(paths)
    return {
        "process": process_name,
        "n_sims": n,
        "p_breach": n_breach / n,
        "mean_time_to_breach": statistics.mean(breach_months) if breach_months else None,
        "median_time_to_breach": statistics.median(breach_months) if breach_months else None,
        "min_dscr_cvar": cvar(min_dscrs, CVAR_TAIL_FRACTION),
        "min_dscr_mean": statistics.mean(min_dscrs),
    }


def main():
    n_sims = int(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_N_SIMS

    debt_terms = io.load_debt_terms()
    company_financials = io.load_company_financials()
    useful_life_rows = io.load_useful_life_assumptions()
    rental_history_rows = io.load_rental_rate_history()
    opex_calibration = io.load_opex_calibration()

    power_cost = float(opex_calibration["h100_power_cooling_cost_usd_per_hr"])
    raw_calibration = model.calibrate(debt_terms, useful_life_rows, rental_history_rows, company_financials, power_cost)
    calibration = model.scale_to_covenant_clearing(raw_calibration)
    n = calibration["amortization_months"]

    monthly_returns = decay.historical_monthly_log_returns(rental_history_rows)
    print(f"historical calibration: {len(monthly_returns)} monthly-equivalent log-return observations")
    print(f"  (derived from {len(rental_history_rows)} period medians in rental_rate_history.csv)")
    print(f"  observations: {[round(r, 4) for r in monthly_returns]}")
    print(f"  THIS IS SPARSE. Every process below inherits that sparsity -- see README.\n")

    rng = random.Random(SEED)

    gbm_sim_paths, gbm_params = decay.gbm_paths(n, n_sims, monthly_returns, rng)
    print(f"GBM params: monthly drift={gbm_params['monthly_drift']:.4f}, vol={gbm_params['monthly_vol']:.4f}")

    bootstrap_sim_paths, bootstrap_params = decay.block_bootstrap_paths(n, n_sims, monthly_returns, rng)
    print(f"Block bootstrap params: block_size={bootstrap_params['block_size']}, "
          f"source_obs={bootstrap_params['n_source_obs']}")

    regime_sim_paths, regime_params = decay.regime_switching_paths(n, n_sims, monthly_returns, rng)
    print(f"Regime-switching params: switch_prob/month={regime_params['switch_prob_per_month']:.3f} "
          f"(from only {regime_params['n_transitions_observed']} observed transitions in "
          f"{regime_params['n_observations']} observations -- treat this process's output with the most caution)")

    results = [
        simulate("gbm", gbm_sim_paths, calibration),
        simulate("block_bootstrap", bootstrap_sim_paths, calibration),
        simulate("regime_switching", regime_sim_paths, calibration),
    ]

    print(f"\n{n_sims} simulated paths per process, {n}-month horizon, seed={SEED} (reproducible)\n")
    print(f"{'process':<18}{'P(breach)':>11}{'median t2b':>12}{'min-DSCR CVaR10%':>18}")
    for r in results:
        t2b = f"{r['median_time_to_breach']:.0f}mo" if r["median_time_to_breach"] else "n/a"
        print(f"{r['process']:<18}{r['p_breach']*100:>10.1f}%{t2b:>12}{r['min_dscr_cvar']:>18.2f}")

    max_ltv_deterministic = max(
        row["ltv"] for row in model.run_waterfall(calibration, [1.0] * n)
    )
    print(f"\nmax LTV over the loan's life: {max_ltv_deterministic:.3f} -- IDENTICAL regardless of rate-decay")
    print("process or scenario. Collateral is modeled via CoreWeave's own straight-line, no-salvage")
    print("book-depreciation policy, and the loan amortizes on a fixed schedule -- neither is tied to")
    print("rental-rate performance in this model, so LTV never responds to the stochastic simulation.")
    print("Flagged as a real simplification, not a finding -- see README 'What this model doesn't capture.'")

    p_breaches = [r["p_breach"] for r in results]
    spread = max(p_breaches) - min(p_breaches)
    print(f"\nP(breach) spread across the three processes: {spread*100:.1f} percentage points.")
    if spread > 0.15:
        print("That's a wide spread -- the breach-risk conclusion is sensitive to which process you trust,")
        print("which given the sparse calibration data, this analysis can't resolve on its own.")
    else:
        print("The three processes broadly agree despite different structural assumptions -- a more")
        print("robust signal than any single process alone, even given the sparse calibration data.")


if __name__ == "__main__":
    main()
