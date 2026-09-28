"""Load the CSVs this sub-project reads -- curated power/electricity/PUE
reference data plus the cached output of the live rental puller."""
import csv
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "data"


def _read_csv(path):
    with open(path, newline="") as f:
        return list(csv.DictReader(f))


def load_gpu_power_draw():
    return _read_csv(DATA_DIR / "gpu_power_draw.csv")


def load_electricity_prices():
    return _read_csv(DATA_DIR / "electricity_prices.csv")


def load_pue_assumptions():
    return _read_csv(DATA_DIR / "pue_assumptions.csv")


def load_gpu_rental():
    return _read_csv(DATA_DIR / "gpu_rental.csv")


def load_history():
    path = DATA_DIR / "history" / "shutdown_floor_snapshots.csv"
    if not path.exists():
        return []
    return _read_csv(path)
