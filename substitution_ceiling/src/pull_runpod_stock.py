"""Pull live GPU stock-status signal from RunPod's public GraphQL endpoint.

No API key required for this query. This is a secondary, independent market
used only as a corroborating supply signal for the substitution ceiling
result -- see README.md "Supply signal" section for why and its limits.

Note: stockStatus == null means RunPod has no live-priced offer for that GPU
right now. That's consistent with two different underlying stories this
signal alone can't distinguish -- (a) existing installed capacity is fully
rented, or (b) RunPod hasn't deployed/onboarded that chip yet. Flagged, not
resolved, in the README.
"""
import csv
from pathlib import Path

import requests

RUNPOD_URL = "https://api.runpod.io/graphql"

RUNPOD_QUERY = """
query GpuTypes {
  gpuTypes {
    displayName
    lowestPrice(input: {gpuCount: 1}) {
      minimumBidPrice
      uninterruptablePrice
      stockStatus
    }
  }
}
"""

# RunPod's displayName -> canonical GPU label used across this sub-project.
GPU_NAME_MAP = {
    "H100 SXM": "H100 SXM",
    "H200 SXM": "H200 SXM",
    "B200": "B200",
}

OUTPUT_PATH = Path(__file__).resolve().parent.parent / "data" / "runpod_stock.csv"


def fetch_gpu_types():
    resp = requests.post(RUNPOD_URL, json={"query": RUNPOD_QUERY}, timeout=20)
    resp.raise_for_status()
    return resp.json()["data"]["gpuTypes"]


def summarize(gpu_types, snapshot_date):
    by_name = {g["displayName"]: g for g in gpu_types}
    rows = []
    for raw_name, canonical in GPU_NAME_MAP.items():
        g = by_name.get(raw_name)
        if g is None:
            continue
        price = g["lowestPrice"]
        rows.append(
            {
                "gpu": canonical,
                "stock_status": price.get("stockStatus"),
                "lowest_price_usd_per_hr": price.get("uninterruptablePrice"),
                "source": "runpod_api",
                "snapshot_date": snapshot_date,
            }
        )
    return rows


def pull_runpod_stock(snapshot_date, write=True):
    gpu_types = fetch_gpu_types()
    rows = summarize(gpu_types, snapshot_date)
    if write:
        with open(OUTPUT_PATH, "w", newline="") as f:
            writer = csv.DictWriter(
                f, fieldnames=["gpu", "stock_status", "lowest_price_usd_per_hr", "source", "snapshot_date"]
            )
            writer.writeheader()
            writer.writerows(rows)
    return rows


if __name__ == "__main__":
    import datetime

    today = datetime.date.today().isoformat()
    for row in pull_runpod_stock(today):
        print(row)
