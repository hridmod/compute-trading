"""Load the CSVs this sub-project reads -- curated benchmark data plus the
cached output of the live rental puller."""
import csv
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "data"


def _read_csv(path):
    with open(path, newline="") as f:
        return list(csv.DictReader(f))


def load_mlperf_benchmarks():
    return _read_csv(DATA_DIR / "mlperf_benchmarks.csv")


def load_gpu_rental():
    return _read_csv(DATA_DIR / "gpu_rental.csv")


def load_runpod_stock():
    return _read_csv(DATA_DIR / "runpod_stock.csv")


def load_history():
    path = DATA_DIR / "history" / "substitution_snapshots.csv"
    if not path.exists():
        return []
    return _read_csv(path)


def load_supply_signal_history():
    path = DATA_DIR / "history" / "supply_signals.csv"
    if not path.exists():
        return []
    return _read_csv(path)
