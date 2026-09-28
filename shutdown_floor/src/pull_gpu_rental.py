"""Pull live on-demand GPU rental prices from the Vast.ai public marketplace API.

No API key required -- this hits the same public search endpoint the
Vast.ai console uses (https://cloud.vast.ai/api/v0/bundles/).
"""
import csv
import json
from pathlib import Path

import requests

VASTAI_URL = "https://cloud.vast.ai/api/v0/bundles/"

# Vast.ai's raw gpu_name -> canonical GPU label used across this sub-project
# (must match the `gpu` column in data/mlperf_benchmarks.csv).
GPU_NAME_MAP = {
    "H100 SXM": "H100 SXM",
    "H200": "H200 SXM",
    "B200": "B200",
}

OUTPUT_PATH = Path(__file__).resolve().parent.parent / "data" / "gpu_rental.csv"


def fetch_offers():
    query = {
        "gpu_name": {"in": list(GPU_NAME_MAP.keys())},
        "rentable": {"eq": True},
        "num_gpus": {"eq": 1},
        "verified": {"eq": True},
        "type": "on-demand",
        "order": [["dph_total", "asc"]],
    }
    resp = requests.get(VASTAI_URL, params={"q": json.dumps(query)}, timeout=20)
    resp.raise_for_status()
    return resp.json().get("offers", [])


def summarize(offers, snapshot_date):
    """Collapse raw per-instance offers into one min/median/max row per GPU."""
    by_gpu = {}
    for o in offers:
        canonical = GPU_NAME_MAP.get(o["gpu_name"])
        if canonical is None:
            continue
        by_gpu.setdefault(canonical, []).append(o["dph_total"])

    rows = []
    for gpu, prices in sorted(by_gpu.items()):
        prices = sorted(prices)
        n = len(prices)
        median = prices[n // 2] if n % 2 else (prices[n // 2 - 1] + prices[n // 2]) / 2
        rows.append(
            {
                "gpu": gpu,
                "n_offers": n,
                "dph_min": round(prices[0], 4),
                "dph_median": round(median, 4),
                "dph_max": round(prices[-1], 4),
                "source": "vastai_api",
                "snapshot_date": snapshot_date,
            }
        )
    return rows


def pull_gpu_rental(snapshot_date, write=True):
    offers = fetch_offers()
    rows = summarize(offers, snapshot_date)
    if write:
        with open(OUTPUT_PATH, "w", newline="") as f:
            writer = csv.DictWriter(
                f, fieldnames=["gpu", "n_offers", "dph_min", "dph_median", "dph_max", "source", "snapshot_date"]
            )
            writer.writeheader()
            writer.writerows(rows)
    return rows


if __name__ == "__main__":
    import datetime

    today = datetime.date.today().isoformat()
    for row in pull_gpu_rental(today):
        print(row)
