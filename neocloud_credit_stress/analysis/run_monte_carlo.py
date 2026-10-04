"""Monte Carlo: simulate many future rental-rate paths via block bootstrap
(resampling real historical month-over-month moves), run each through the
DSCR/LTV waterfall, and report the distribution of outcomes.

Block bootstrap only -- not compared against GBM or regime-switching here.
An earlier version ran all three; regime-switching's breach probability
(87%) was wildly higher than the other two (25-46%), and its calibration
rests on just 2 observed transitions in 4 data points -- not enough to
trust. Rather than keep reporting an unstable number alongside two more
trustworthy ones, this version keeps only block bootstrap: it directly
resamples real historical moves, so it doesn't require assuming a
distribution or a transition structure the data can't actually support.

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

SEED = 20261004  # fixed for reproducibility -- same seed always reproduces this result exactly
DEFAULT_N_SIMS = 2000
CVAR_TAIL_FRACTION = 0.10


def cvar(values, tail_fraction):
    """Expected value of the worst tail_fraction of values (lower = worse
    here, so CVaR of DSCR = average of the worst/lowest DSCR outcomes)."""
    ordered = sorted(values)
    n_tail = max(1, int(len(ordered) * tail_fraction))
    return sum(ordered[:n_tail]) / n_tail


def main():
    n_sims = int(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_N_SIMS

    debt_terms = io.load_debt_terms()
    company_financials = io.load_company_financials()
    useful_life_rows = io.load_useful_life_assumptions()
    rental_history_rows = io.load_rental_rate_history()
    opex_calibration = io.load_opex_calibration()
    fleet_calibration = io.load_fleet_calibration()

    power_cost = float(opex_calibration["h100_power_cooling_cost_usd_per_hr"])
    calibration = model.calibrate(
        debt_terms, useful_life_rows, rental_history_rows, fleet_calibration, company_financials, power_cost
    )
    n = calibration["amortization_months"]

    monthly_returns = decay.historical_monthly_log_returns(rental_history_rows)
    print(f"historical calibration: {len(monthly_returns)} monthly-equivalent log-return observations")
    print(f"  (derived from {len(rental_history_rows)} period medians in rental_rate_history.csv)")
    print(f"  observations: {[round(r, 4) for r in monthly_returns]}")
    print("  THIS IS SPARSE -- every result below inherits that sparsity, see README.\n")

    rng = random.Random(SEED)
    paths, params = decay.block_bootstrap_paths(n, n_sims, monthly_returns, rng)
    print(f"block bootstrap params: block_size={params['block_size']}, source_obs={params['n_source_obs']}")

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

    print(f"\n{n_sims} simulated paths, {n}-month horizon, seed={SEED} (reproducible)\n")
    print(f"breaches observed:      {n_breach} / {n_sims}  (NOT the same as 'impossible' -- see worst-case check below)")
    if breach_months:
        print(f"median time to breach:  {statistics.median(breach_months):.0f} months")
    print(f"min-DSCR, mean:          {statistics.mean(min_dscrs):.2f}x")
    print(f"min-DSCR, worst 10% avg (CVaR): {cvar(min_dscrs, CVAR_TAIL_FRACTION):.2f}x")

    worst_observed_move = min(monthly_returns)
    worst_case_path = [1.0]
    for _ in range(1, n):
        worst_case_path.append(worst_case_path[-1] * (2.718281828 ** worst_observed_move))
    worst_rows = model.run_waterfall(calibration, worst_case_path)
    worst_summary = model.summarize_run(worst_rows, calibration["dscr_covenant"])
    print(f"\nstructural check: bootstrap can only recombine the {len(monthly_returns)} historical moves it was given --")
    print(f"it cannot invent a shock worse than what's already in that sample. Repeating the single worst")
    print(f"observed month ({worst_observed_move*100:.2f}%/mo) for all {n} months straight -- an astronomically")
    print(f"unlikely draw, but the genuine ceiling on how bad this method could ever show -- gives min DSCR "
          f"{worst_summary['min_dscr']:.2f}x, breach = {worst_summary['any_breach']}.")
    print("Zero breaches in simulation does not mean zero risk: it means no risk beyond what 4 historical")
    print("data points can describe. A real shock outside that envelope isn't represented here at all.")


if __name__ == "__main__":
    main()
