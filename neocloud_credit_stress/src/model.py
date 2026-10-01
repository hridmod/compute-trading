"""Structural credit model for CoreWeave's DDTL V-V facility ($2.6B, 1.35x
DSCR covenant) -- per-capex-dollar normalized, since the tranche's exact GPU
count/mix isn't disclosed (see README "Why per-capex-dollar").

Calibration (baseline, t=0):
    revenue_to_debt_ratio   = FY2025 whole-company revenue / whole-company total debt
    baseline_annual_revenue = loan_amount * revenue_to_debt_ratio
    baseline_ebitda_margin  = FY2025 whole-company adjusted EBITDA margin (60%)
    rate_baseline           = most recent neocloud-tier $/hr (Silicon Data)
    implied_fleet_hours     = baseline_annual_revenue / rate_baseline

Monthly waterfall, given a rate_index path (1.0 = baseline, moves with the
decay process driving the simulation):
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

The power/cooling component of opex is NOT a separate line item in this
waterfall -- it's a small (~5%, see README) slice of the fixed opex figure,
sized using shutdown_floor's own verified H100 floor ($0.063/hr,
most_efficient scenario) at the baseline rate. Shown separately in
calibration output for transparency, not because it moves independently.
"""

def calibrate(debt_terms, useful_life_rows, rental_history_rows, company_financials, power_cost_usd_per_hr):
    loan_amount = float(debt_terms["facility_size_usd"])
    revenue = float(company_financials["fy2025_revenue_usd"])
    total_debt = float(company_financials["total_debt_usd"])
    ebitda_margin = float(company_financials["fy2025_adj_ebitda_margin_pct"]) / 100

    revenue_to_debt_ratio = revenue / total_debt
    baseline_annual_revenue = loan_amount * revenue_to_debt_ratio
    baseline_annual_opex_total = baseline_annual_revenue * (1 - ebitda_margin)

    rate_baseline = float(rental_history_rows[-1]["price_median_usd_per_hr"])
    implied_fleet_hours_per_year = baseline_annual_revenue / rate_baseline

    baseline_annual_power_opex = implied_fleet_hours_per_year * power_cost_usd_per_hr

    coreweave_life = next(r for r in useful_life_rows if r["company"] == "CoreWeave")
    useful_life_months = float(coreweave_life["useful_life_years"]) * 12

    return {
        "loan_amount": loan_amount,
        "revenue_to_debt_ratio": revenue_to_debt_ratio,
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


def required_efficiency_multiple(calibration):
    """How many times the whole-company-blended revenue-to-debt ratio would
    this tranche need to generate, at today's rate (rate_index=1.0), for
    month-1 DSCR to clear the covenant exactly?

    The proportional/blended calibration in calibrate() applies CoreWeave's
    company-wide average revenue-per-debt-dollar to this one tranche. But
    this tranche's terms (full 5yr amortization, 550bps spread) are far
    harsher than the company's blended average debt profile, and it's
    specifically backed by newer, individually-underwritten customer
    contracts (per the facility's own disclosure) -- not a cross-section of
    the whole book. So the blended calibration likely understates what this
    tranche's actual backing revenue is. This multiple quantifies exactly
    how far off: a company backing a loan this tight would need contracts
    performing at N times the company average to clear covenant today, with
    zero rate decay yet applied.
    """
    n = calibration["amortization_months"]
    monthly_principal = calibration["loan_amount"] / n
    monthly_rate = (calibration["sofr_pct"] / 100 + calibration["spread_bps"] / 10000) / 12
    month1_interest = calibration["loan_amount"] * monthly_rate
    month1_debt_service = monthly_principal + month1_interest
    monthly_opex = calibration["baseline_annual_opex_total"] / 12

    required_monthly_revenue = calibration["dscr_covenant"] * month1_debt_service + monthly_opex
    required_annual_revenue = required_monthly_revenue * 12
    return required_annual_revenue / calibration["baseline_annual_revenue"]


def scale_to_covenant_clearing(calibration):
    """Return a copy of calibration scaled so month-1 DSCR sits exactly at
    the covenant (1.35x) with zero rate decay -- i.e. assume this tranche's
    specific contracts realize a higher effective $/hr than the general
    neocloud-tier market median (consistent with guaranteed/reserved
    capacity commanding a premium over spot -- the L3 firmness/workload
    distinction from PROJECT_BRIEF.md's commodity hierarchy), rather than
    the company-blended average.

    Deliberately scales ONLY revenue, not opex or implied fleet hours: the
    physical fleet (and what it costs to power/cool/operate) is pinned by
    the $2.6B of capex regardless of what price its output is contracted
    at. Scaling opex too would have been inconsistent with how
    required_efficiency_multiple() computed the required revenue (against
    UNSCALED opex) -- that mismatch was caught by hand-verifying month-1
    DSCR came out well below 1.35x instead of exactly at it.

    Use this calibration for decay scenario / Monte Carlo comparisons: it
    isolates the effect of rate decay from the baseline-tightness finding
    above, which is a separate issue."""
    multiple = required_efficiency_multiple(calibration)
    scaled = dict(calibration)
    scaled["baseline_annual_revenue"] = calibration["baseline_annual_revenue"] * multiple
    scaled["_scaled_by_multiple"] = multiple
    return scaled


BREACH_TOLERANCE = 1e-6  # see run_waterfall docstring


def run_waterfall(calibration, rate_index_path):
    """rate_index_path: list of monthly multipliers, rate_index_path[0] ~ 1.0
    is baseline. Length determines the simulation horizon (should match
    calibration['amortization_months'] for a full-tenor run).

    Breach uses dscr < dscr_covenant - BREACH_TOLERANCE, not a bare `<`.
    Caught this the hard way: scale_to_covenant_clearing() is supposed to
    put month-1 DSCR at exactly the covenant with zero decay, but the real
    float value came out as 1.34999999999999986677 against a covenant of
    1.35000000000000008882 -- a ~2e-16 gap from floating-point error
    accumulated through the calibration chain, not an economic finding.
    Bare `<` flagged every "exactly at covenant" case as a breach."""
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
