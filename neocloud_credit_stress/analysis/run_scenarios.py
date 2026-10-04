"""Deterministic sanity check: run the DSCR/LTV waterfall at today's rate,
then under one realistic shaped shock (step down + partial reversal,
calibrated to the real historical neocloud-tier move). Validates the
model's mechanics before run_monte_carlo.py's stochastic comparison.

Usage: python analysis/run_scenarios.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src import decay_processes as decay  # noqa: E402
from src import io  # noqa: E402
from src import model  # noqa: E402


def main():
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

    print("calibration (bottom-up from hardware cost):")
    print(f"  cost per GPU:            ${calibration['cost_per_gpu']:,.0f}")
    print(f"  implied fleet size:      {calibration['fleet_size']:,.0f} GPUs")
    print(f"  utilization assumed:     {calibration['utilization']*100:.0f}%")
    print(f"  implied fleet-hours/yr:  {calibration['implied_fleet_hours_per_year']/1e6:,.1f}M")
    print(f"  rate baseline:           ${calibration['rate_baseline']:.2f}/hr (neocloud tier)")
    print(f"  implied annual revenue:  ${calibration['baseline_annual_revenue']/1e6:,.1f}M")
    print(f"  implied annual opex:     ${calibration['baseline_annual_opex_total']/1e6:,.1f}M")
    print(f"  of which power/cooling:  ${calibration['baseline_annual_power_opex']/1e6:,.2f}M "
          f"({calibration['power_opex_share_of_total']*100:.1f}% of total opex)")
    print(f"  amortization horizon:    {calibration['amortization_months']} months")
    print(f"  DSCR covenant:           {calibration['dscr_covenant']}x")

    n = calibration["amortization_months"]

    flat_rows = model.run_waterfall(calibration, [1.0] * n)
    flat_summary = model.summarize_run(flat_rows, calibration["dscr_covenant"])
    print(f"\nflat (today's rate, no decay): month-1 DSCR = {flat_rows[0]['dscr']:.2f}x, "
          f"breach = {flat_summary['any_breach']}")

    shock_path = decay.stair_step_with_reversal(n)
    shock_rows = model.run_waterfall(calibration, shock_path)
    shock_summary = model.summarize_run(shock_rows, calibration["dscr_covenant"])
    print(f"step-down + partial reversal (6% down @ mo18, 5% back @ mo30):")
    print(f"  min DSCR {shock_summary['min_dscr']:.2f}x @ month {shock_summary['min_dscr_month']}, "
          f"breach = {shock_summary['any_breach']}"
          + (f" (first @ month {shock_summary['first_breach_month']})" if shock_summary["any_breach"] else ""))


if __name__ == "__main__":
    main()
