"""Run the shutdown floor test on a fresh snapshot, under two scenarios.

Usage:
    python analysis/run_analysis.py          # pull live rental data, run test, append to history
    python analysis/run_analysis.py --no-pull  # reuse cached data/gpu_rental.csv, run test only
"""
import argparse
import csv
import datetime
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src import io  # noqa: E402
from src import model  # noqa: E402
from src.pull_gpu_rental import pull_gpu_rental  # noqa: E402

SCENARIOS = [
    # (scenario_name, region, pue_metric)
    ("toughest", "Virginia", "pue_per_site_average"),
    ("most_efficient", "Texas", "pue_capacity_weighted"),
]

HISTORY_PATH = Path(__file__).resolve().parent.parent / "data" / "history" / "shutdown_floor_snapshots.csv"
HISTORY_FIELDS = [
    "snapshot_date",
    "scenario",
    "gpu",
    "tdp_watts",
    "pue",
    "electricity_usd_per_kwh",
    "floor_usd_per_hr",
    "rental_usd_per_hr",
    "ratio",
    "violation",
]


def append_history(results, snapshot_date):
    HISTORY_PATH.parent.mkdir(parents=True, exist_ok=True)
    is_new = not HISTORY_PATH.exists()
    with open(HISTORY_PATH, "a", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=HISTORY_FIELDS)
        if is_new:
            writer.writeheader()
        for r in results:
            writer.writerow({"snapshot_date": snapshot_date, **r})


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--no-pull", action="store_true", help="reuse cached data/gpu_rental.csv instead of pulling live")
    args = parser.parse_args()

    today = datetime.date.today().isoformat()

    if not args.no_pull:
        print(f"pulling live data ({today})...")
        pull_gpu_rental(today)

    power_rows = io.load_gpu_power_draw()
    price_rows = io.load_electricity_prices()
    pue_rows = io.load_pue_assumptions()
    rental_rows = io.load_gpu_rental()

    all_results = []
    for scenario_name, region, pue_metric in SCENARIOS:
        results = model.compute_shutdown_floor_test(
            power_rows, price_rows, pue_rows, rental_rows, region, pue_metric, scenario_name
        )
        all_results.extend(results)

        print(f"\nshutdown floor test -- {today} -- scenario: {scenario_name} ({region} electricity, {pue_metric})")
        if not results:
            print("  no results (need power draw + electricity + rental quote for at least one GPU)")
            continue
        print(f"{'gpu':<12}{'rental $/hr':>14}{'floor $/hr':>13}{'ratio':>10}  violation")
        for r in results:
            print(
                f"{r['gpu']:<12}{r['rental_usd_per_hr']:>14.3f}{r['floor_usd_per_hr']:>13.4f}"
                f"{r['ratio']:>10.1f}  {r['violation']}"
            )

    append_history(all_results, today)
    print(f"\nappended {len(all_results)} row(s) to {HISTORY_PATH}")


if __name__ == "__main__":
    main()
