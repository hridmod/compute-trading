"""Backtest the substitution ceiling across every accumulated snapshot in
data/history/substitution_snapshots.csv.

Each run of run_analysis.py appends one row per legacy GPU for that day.
Run this on a cadence (see .github/workflows/daily_snapshot.yml) to see
whether legacy SKUs stay in backwardation (below the ceiling, as expected
by default) or drift into contango (above it) -- the source thesis frames
a legacy-chip curve printing in contango as the informative signal.
"""
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src import io  # noqa: E402


def main():
    history = io.load_history()
    if not history:
        print("no history yet -- run analysis/run_analysis.py at least once first")
        return

    by_gpu = defaultdict(list)
    for row in history:
        by_gpu[row["gpu"]].append(row)

    n_dates = len({row["snapshot_date"] for row in history})
    print(f"backtest: {n_dates} snapshot date(s), {len(history)} total observations\n")

    for gpu, rows in sorted(by_gpu.items()):
        rows = sorted(rows, key=lambda r: r["snapshot_date"])
        ratios = [float(r["ratio"]) for r in rows]
        violations = sum(1 for r in rows if r["violation"] == "True")
        print(f"{gpu} vs {rows[-1]['best_chip']}: {len(rows)} observation(s), {violations} violation(s)")
        print(f"  ratio range: {min(ratios):.3f} - {max(ratios):.3f} (rental / substitution ceiling)")
        for r in rows:
            flag = " <-- VIOLATION (contango vs best chip)" if r["violation"] == "True" else ""
            print(f"  {r['snapshot_date']}  ratio={float(r['ratio']):.3f}{flag}")
        print()

    if n_dates < 2:
        print(
            "note: only one snapshot date accumulated so far -- this is a cross-sectional "
            "snapshot, not yet a real time-series backtest. Run run_analysis.py again on a "
            "later date (or let the scheduled GitHub Action accumulate history) to get a "
            "genuine backtest."
        )


if __name__ == "__main__":
    main()
