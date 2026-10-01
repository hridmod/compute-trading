"""Stage 1: run the DSCR/LTV waterfall under three deterministic rate-index
scenarios. Fast, no randomness -- validates the model mechanics before
Stage 2's Monte Carlo comparison.

Usage: python analysis/run_scenarios.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src import decay_processes as decay  # noqa: E402
from src import io  # noqa: E402
from src import model  # noqa: E402


def print_calibration(label, calibration):
    print(f"calibration -- {label}:")
    print(f"  implied annual revenue:  ${calibration['baseline_annual_revenue']/1e6:,.1f}M")
    print(f"  implied annual opex:     ${calibration['baseline_annual_opex_total']/1e6:,.1f}M")
    print(f"  of which power/cooling:  ${calibration['baseline_annual_power_opex']/1e6:,.2f}M "
          f"({calibration['power_opex_share_of_total']*100:.1f}% of total opex)")
    print(f"  implied fleet-hours/yr:  {calibration['implied_fleet_hours_per_year']/1e6:,.1f}M")
    print(f"  rate baseline:           ${calibration['rate_baseline']:.2f}/hr (neocloud tier)")


def main():
    debt_terms = io.load_debt_terms()
    company_financials = io.load_company_financials()
    useful_life_rows = io.load_useful_life_assumptions()
    rental_history_rows = io.load_rental_rate_history()
    opex_calibration = io.load_opex_calibration()

    power_cost = float(opex_calibration["h100_power_cooling_cost_usd_per_hr"])
    raw_calibration = model.calibrate(debt_terms, useful_life_rows, rental_history_rows, company_financials, power_cost)

    print_calibration("proportional (whole-company-blended revenue/debt ratio)", raw_calibration)
    print(f"  amortization horizon:    {raw_calibration['amortization_months']} months")
    print(f"  DSCR covenant:           {raw_calibration['dscr_covenant']}x")

    raw_rows = model.run_waterfall(raw_calibration, [1.0] * raw_calibration["amortization_months"])
    print(f"\n  DSCR at month 1, ZERO rate decay applied: {raw_rows[0]['dscr']:.3f}x "
          f"(covenant: {raw_calibration['dscr_covenant']}x)")

    multiple = model.required_efficiency_multiple(raw_calibration)
    print(f"\n  FINDING: at the whole-company-blended revenue allocation, this tranche's\n"
          f"  baseline DSCR is already below covenant -- before any rate decay. This tranche\n"
          f"  would need to generate {multiple:.2f}x the company-average revenue-per-debt-dollar\n"
          f"  to clear 1.35x DSCR today. Plausible: the facility is specifically backed by\n"
          f"  newer, individually-underwritten customer contracts (per its own disclosure),\n"
          f"  not a cross-section of the whole book -- but that {multiple:.1f}x isn't something\n"
          f"  this data can confirm or rule out. Flagged as the key open question, not resolved.")

    scaled_calibration = model.scale_to_covenant_clearing(raw_calibration)
    print(f"\n{'='*70}")
    print("Scenario comparison below uses the SCALED calibration (assumes this\n"
          "tranche's contracts perform at exactly the required efficiency multiple,\n"
          "i.e. DSCR = 1.35x exactly at t=0) -- this isolates rate-decay risk from\n"
          "the baseline-tightness finding above, which is a separate question.")
    print(f"{'='*70}\n")

    n = scaled_calibration["amortization_months"]
    scenarios = {
        "smooth_decline": decay.smooth_decline(n, monthly_decline_rate=0.01),
        "stair_step_with_reversal": decay.stair_step_with_reversal(n),
        "aggressive_decline": decay.aggressive_decline(n, monthly_decline_rate=0.025),
    }

    print(f"{'scenario':<28}{'min DSCR':>10}{'@month':>8}{'breach?':>9}{'1st breach':>12}{'max LTV':>10}")
    for name, path in scenarios.items():
        rows = model.run_waterfall(scaled_calibration, path)
        summary = model.summarize_run(rows, scaled_calibration["dscr_covenant"])
        print(
            f"{name:<28}{summary['min_dscr']:>10.2f}{summary['min_dscr_month']:>8}"
            f"{str(summary['any_breach']):>9}{str(summary['first_breach_month']):>12}"
            f"{summary['max_ltv']:>10.3f}"
        )


if __name__ == "__main__":
    main()
