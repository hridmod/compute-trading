"""Shutdown floor model.

Hypothesis (thesis claim, see PROJECT_BRIEF.md #6): a forward can't
sustainably print below the marginal operator's variable cash cost --
power, colo, staffing. Below it, capacity withdraws rather than sells,
identical to the retirement condition on a power plant.

    floor_usd_per_hr = (tdp_watts / 1000) * PUE * electricity_usd_per_kwh

    ratio = rental_usd_per_hr / floor_usd_per_hr

ratio < 1.0 is a floor violation: rental is printing below what it costs
just to power and cool the chip -- unsustainable, capacity should withdraw.

PUE (power usage effectiveness) scales raw chip power draw up to total
facility power draw, capturing cooling/electrical overhead -- a real,
non-trivial cost component that raw TDP alone misses.

Explicitly excluded: colo lease cost and staffing. The thesis names both as
real components of variable cash cost, but neither has a defensible public
per-GPU-hour figure the way power and PUE do. Excluding them makes this
floor a **lower bound** -- the true floor is at least this high, likely
somewhat higher. That biases the test toward *not* finding a violation, so
if a violation is ever found despite this, it's a strong signal; a "not
violated" result here doesn't fully rule one out once real costs are added.

Two scenarios are computed, same "pick the toughest test" convention used
in token_parity/substitution_ceiling:
- toughest: highest electricity price (Virginia) x highest PUE (per-site
  average) -- most likely to show a violation if one exists.
- most_efficient: lowest electricity price (Texas) x lowest PUE
  (capacity-weighted) -- most realistic for large hyperscale-class fleets,
  least likely to show a violation.
"""

WATTS_PER_KW = 1000


def tdp_watts(power_rows, gpu):
    for r in power_rows:
        if r["gpu"] == gpu:
            return float(r["tdp_watts"])
    return None


def electricity_price(price_rows, region):
    for r in price_rows:
        if r["region"] == region:
            return float(r["price_usd_per_kwh"])
    return None


def pue_value(pue_rows, metric):
    for r in pue_rows:
        if r["metric"] == metric:
            return float(r["value"])
    return None


def floor_usd_per_hr(tdp_w, pue, electricity_usd_per_kwh):
    return (tdp_w / WATTS_PER_KW) * pue * electricity_usd_per_kwh


def compute_shutdown_floor_test(power_rows, price_rows, pue_rows, rental_rows, region, pue_metric, scenario_name):
    electricity = electricity_price(price_rows, region)
    pue = pue_value(pue_rows, pue_metric)
    if electricity is None or pue is None:
        raise ValueError(f"missing electricity price for {region!r} or PUE for {pue_metric!r}")

    results = []
    for rental in rental_rows:
        gpu = rental["gpu"]
        tdp = tdp_watts(power_rows, gpu)
        if tdp is None:
            continue
        floor = floor_usd_per_hr(tdp, pue, electricity)
        rental_usd_per_hr = float(rental["dph_median"])
        results.append(
            {
                "scenario": scenario_name,
                "gpu": gpu,
                "tdp_watts": tdp,
                "pue": pue,
                "electricity_usd_per_kwh": electricity,
                "floor_usd_per_hr": round(floor, 4),
                "rental_usd_per_hr": rental_usd_per_hr,
                "ratio": round(rental_usd_per_hr / floor, 4),
                "violation": rental_usd_per_hr < floor,
            }
        )
    return results
