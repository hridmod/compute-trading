"""Run the substitution ceiling test on a fresh snapshot.

Usage:
    python analysis/run_analysis.py          # pull live data, run test, append to history
    python analysis/run_analysis.py --no-pull  # reuse cached data/*.csv, run test only
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

HISTORY_PATH = Path(__file__).resolve().parent.parent / "data" / "history" / "substitution_snapshots.csv"
HISTORY_FIELDS = [
    "snapshot_date",
    "gpu",
    "best_chip",
    "offline_tokens_per_sec",
    "best_chip_tokens_per_sec",
    "best_chip_rental_usd_per_hr",
    "ceiling_usd_per_hr",
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
    parser.add_argument("--no-pull", action="store_true", help="reuse cached data/*.csv instead of pulling live")
    args = parser.parse_args()

    today = datetime.date.today().isoformat()

    if not args.no_pull:
        print(f"pulling live data ({today})...")
        pull_gpu_rental(today)

    mlperf_rows = io.load_mlperf_benchmarks()
    rental_rows = io.load_gpu_rental()

    results = model.compute_substitution_test(mlperf_rows, rental_rows)

    print(f"\nsubstitution ceiling test -- {today}")
    if not results:
        print("no results (need at least 2 GPUs with both a benchmark and a rental quote)")
        return
    print(f"best chip: {results[0]['best_chip']} ({results[0]['best_chip_tokens_per_sec']} tok/s/GPU, ${results[0]['best_chip_rental_usd_per_hr']}/hr)")
    print(f"{'gpu':<12}{'rental $/hr':>14}{'ceiling $/hr':>16}{'ratio':>10}  violation")
    for r in results:
        print(
            f"{r['gpu']:<12}{r['rental_usd_per_hr']:>14.3f}{r['ceiling_usd_per_hr']:>16.3f}"
            f"{r['ratio']:>10.3f}  {r['violation']}"
        )

    append_history(results, today)
    print(f"\nappended {len(results)} row(s) to {HISTORY_PATH}")


if __name__ == "__main__":
    main()
