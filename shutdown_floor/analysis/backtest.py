"""Backtest the shutdown floor across every accumulated snapshot in
data/history/shutdown_floor_snapshots.csv.

Each run of run_analysis.py appends one row per GPU per scenario for that
day. Run this on a cadence to see whether rental ever approaches the floor
(it shouldn't, under either the token-parity or substitution ceiling
results already found) or whether the slack shrinks over time.
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

    by_scenario_gpu = defaultdict(list)
    for row in history:
        by_scenario_gpu[(row["scenario"], row["gpu"])].append(row)

    n_dates = len({row["snapshot_date"] for row in history})
    print(f"backtest: {n_dates} snapshot date(s), {len(history)} total observations\n")

    for (scenario, gpu), rows in sorted(by_scenario_gpu.items()):
        rows = sorted(rows, key=lambda r: r["snapshot_date"])
        ratios = [float(r["ratio"]) for r in rows]
        violations = sum(1 for r in rows if r["violation"] == "True")
        print(f"[{scenario}] {gpu}: {len(rows)} observation(s), {violations} violation(s)")
        print(f"  ratio range: {min(ratios):.1f}x - {max(ratios):.1f}x (rental / floor)")
        for r in rows:
            flag = " <-- VIOLATION (below shutdown floor)" if r["violation"] == "True" else ""
            print(f"  {r['snapshot_date']}  ratio={float(r['ratio']):.1f}x{flag}")
        print()

    if n_dates < 2:
        print(
            "note: only one snapshot date accumulated so far -- this is a cross-sectional "
            "snapshot, not yet a real time-series backtest."
        )


if __name__ == "__main__":
    main()
