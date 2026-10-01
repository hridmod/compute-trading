"""Load the sourced reference CSVs this sub-project reads."""
import csv
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "data"


def _read_csv(path):
    with open(path, newline="") as f:
        return list(csv.DictReader(f))


def _read_field_value_csv(path):
    """debt_terms.csv and company_financials.csv are field/value tables,
    not uniform row tables -- collapse to a single dict."""
    return {r["field"]: r["value"] for r in _read_csv(path)}


def load_debt_terms():
    return _read_field_value_csv(DATA_DIR / "debt_terms.csv")


def load_company_financials():
    return _read_field_value_csv(DATA_DIR / "company_financials.csv")


def load_useful_life_assumptions():
    return _read_csv(DATA_DIR / "useful_life_assumptions.csv")


def load_rental_rate_history():
    return _read_csv(DATA_DIR / "rental_rate_history.csv")


def load_opex_calibration():
    return _read_field_value_csv(DATA_DIR / "opex_calibration.csv")
