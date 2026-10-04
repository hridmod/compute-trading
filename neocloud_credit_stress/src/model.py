"""Structural credit model for CoreWeave's DDTL V-V facility ($2.6B, 1.35x
DSCR covenant).

Calibration (baseline, t=0) -- bottom-up from hardware cost, not a
backed-out multiplier against whole-company financials:
    fleet_size        = loan_amount / cost_per_gpu
    fleet_hours/year   = fleet_size * 8760 * utilization
    baseline_revenue  = fleet_hours/year * rate_baseline (neocloud tier)
    baseline_opex     = baseline_revenue * (1 - ebitda_margin)   -- margin is
                         CoreWeave's real disclosed FY2025 figure, applied to
                         revenue this time, not used to size revenue itself
    power_opex        = fleet_hours/year * power_cost_per_hr     -- from
                         shutdown_floor's own verified output

One real assumption chain, each link sourced (see data/fleet_calibration.csv):
hardware cost per GPU -> fleet size -> fleet-hours (at a utilization rate
sourced to how debt-backed, contract-offtake capacity actually runs, not a
generic market-wide figure) -> revenue at the real neocloud-tier rate.

Monthly waterfall, given a rate_index path (1.0 = baseline):
    revenue(t) = (baseline_annual_revenue / 12) * rate_index(t)
    opex(t)    = baseline_annual_opex_total / 12          -- HELD FIXED, see below
    noi(t)     = revenue(t) - opex(t)
    debt_service(t) = straight-line principal + SOFR-indexed interest on
                       declining balance
    dscr(t)    = noi(t) / debt_service(t)                  -- breach if < 1.35x
    collateral(t) = loan_amount * (1 - t / useful_life_months)   -- CoreWeave's
                     own 6yr straight-line, no-salvage policy
    ltv(t)     = outstanding_balance(t) / collateral(t)

Opex is deliberately held FIXED in dollar terms as rate_index falls -- real
opex (bandwidth, staffing, SG&A, non-GPU infra) doesn't shrink just because
rental rates do, at least not on the timescale this model covers. That's
the same "pick the toughest test" convention used in every other
sub-project in this repo: it's the assumption most likely to produce a
covenant breach, so a "not violated" result under it is the stronger claim.

Whatever DSCR comes out at t=0 is reported as-is -- there is no scaling
step to force it to any particular value. An earlier version of this model
backed into revenue via a whole-company ratio, found baseline DSCR deeply
breached, and patched around that with an invented "required efficiency
multiple" to make the decay-scenario comparison runnable. That patch is
gone: this calibration is meant to be defensible on its own, not adjusted
after the fact to produce a convenient starting point.
"""


def calibrate(debt_terms, useful_life_rows, rental_history_rows, fleet_calibration, company_financials, power_cost_usd_per_hr):
    loan_amount = float(debt_terms["facility_size_usd"])

    cost_low = float(fleet_calibration["h100_8gpu_server_cost_low_usd"])
    cost_high = float(fleet_calibration["h100_8gpu_server_cost_high_usd"])
    cost_per_gpu = ((cost_low + cost_high) / 2) / 8
    fleet_size = loan_amount / cost_per_gpu

    utilization = float(fleet_calibration["assumed_utilization_pct"]) / 100
    implied_fleet_hours_per_year = fleet_size * 8760 * utilization

    rate_baseline = float(rental_history_rows[-1]["price_median_usd_per_hr"])
    baseline_annual_revenue = implied_fleet_hours_per_year * rate_baseline

    ebitda_margin = float(company_financials["fy2025_adj_ebitda_margin_pct"]) / 100
    baseline_annual_opex_total = baseline_annual_revenue * (1 - ebitda_margin)

    baseline_annual_power_opex = implied_fleet_hours_per_year * power_cost_usd_per_hr

    coreweave_life = next(r for r in useful_life_rows if r["company"] == "CoreWeave")
    useful_life_months = float(coreweave_life["useful_life_years"]) * 12

    return {
        "loan_amount": loan_amount,
        "cost_per_gpu": cost_per_gpu,
        "fleet_size": fleet_size,
        "utilization": utilization,
        "baseline_annual_revenue": baseline_annual_revenue,
        "baseline_annual_opex_total": baseline_annual_opex_total,
        "baseline_annual_power_opex": baseline_annual_power_opex,
        "power_opex_share_of_total": baseline_annual_power_opex / baseline_annual_opex_total,
        "rate_baseline": rate_baseline,
        "implied_fleet_hours_per_year": implied_fleet_hours_per_year,
        "useful_life_months": useful_life_months,
        "amortization_months": int(debt_terms["amortization_months"]),
        "sofr_pct": float(debt_terms["sofr_pct"]),
        "spread_bps": float(debt_terms["spread_bps_over_sofr"]),
        "dscr_covenant": float(debt_terms["dscr_covenant"]),
    }


BREACH_TOLERANCE = 1e-6  # see run_waterfall docstring


def run_waterfall(calibration, rate_index_path):
    """rate_index_path: list of monthly multipliers, rate_index_path[0] ~ 1.0
    is baseline. Length determines the simulation horizon (should match
    calibration['amortization_months'] for a full-tenor run).

    Breach uses dscr < dscr_covenant - BREACH_TOLERANCE, not a bare `<`.
    Caught this the hard way in an earlier version of this model: a
    calibration meant to sit exactly at the covenant produced a real float
    value of 1.34999999999999986677 against a covenant of
    1.35000000000000008882 -- a ~2e-16 gap from floating-point error, not
    an economic finding. Bare `<` flagged it as a breach anyway."""
    n = calibration["amortization_months"]
    loan_amount = calibration["loan_amount"]
    monthly_principal = loan_amount / n
    monthly_rate = (calibration["sofr_pct"] / 100 + calibration["spread_bps"] / 10000) / 12
    monthly_revenue_base = calibration["baseline_annual_revenue"] / 12
    monthly_opex = calibration["baseline_annual_opex_total"] / 12
    useful_life_months = calibration["useful_life_months"]
    dscr_covenant = calibration["dscr_covenant"]

    rows = []
    balance = loan_amount
    for t in range(1, n + 1):
        idx = min(t - 1, len(rate_index_path) - 1)
        rate_index = rate_index_path[idx]

        revenue = monthly_revenue_base * rate_index
        noi = revenue - monthly_opex

        interest = balance * monthly_rate
        debt_service = monthly_principal + interest
        dscr = noi / debt_service

        balance_after = max(0.0, balance - monthly_principal)
        collateral = loan_amount * max(0.0, 1 - t / useful_life_months)
        ltv = balance_after / collateral if collateral > 0 else float("inf")

        rows.append(
            {
                "month": t,
                "rate_index": round(rate_index, 4),
                "revenue": round(revenue, 2),
                "noi": round(noi, 2),
                "debt_service": round(debt_service, 2),
                "dscr": round(dscr, 4),
                "balance": round(balance_after, 2),
                "collateral": round(collateral, 2),
                "ltv": round(ltv, 4),
                "breach": dscr < dscr_covenant - BREACH_TOLERANCE,
            }
        )
        balance = balance_after

    return rows


def summarize_run(rows, dscr_covenant):
    breaches = [r for r in rows if r["breach"]]
    return {
        "n_months": len(rows),
        "min_dscr": min(r["dscr"] for r in rows),
        "min_dscr_month": min(rows, key=lambda r: r["dscr"])["month"],
        "any_breach": len(breaches) > 0,
        "first_breach_month": breaches[0]["month"] if breaches else None,
        "max_ltv": max(r["ltv"] for r in rows),
        "final_ltv": rows[-1]["ltv"],
    }
