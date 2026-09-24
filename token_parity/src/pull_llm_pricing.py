"""Pull live LLM API token pricing from the OpenRouter public models endpoint.

No API key required for GET /models. We track a fixed basket of ~70B-parameter-
class open-weight instruct models as a proxy for "Llama2-70B-class capability"
token pricing -- see the assumption note in README.md. MLPerf still benchmarks
Llama2-70B itself, but that exact model is no longer commonly metered/served,
so the basket is the closest live market proxy for constant-capability pricing.
"""
import csv
from pathlib import Path

import requests

OPENROUTER_URL = "https://openrouter.ai/api/v1/models"

# Fixed, explicit basket -- not fuzzy-matched -- so it's auditable.
MODEL_BASKET = [
    "meta-llama/llama-3.1-70b-instruct",
    "meta-llama/llama-3.3-70b-instruct",
    "qwen/qwen-2.5-72b-instruct",
    "nousresearch/hermes-3-llama-3.1-70b",
    "mistralai/mixtral-8x22b-instruct",
]

OUTPUT_PATH = Path(__file__).resolve().parent.parent / "data" / "llm_pricing.csv"


def fetch_models():
    resp = requests.get(OPENROUTER_URL, timeout=20)
    resp.raise_for_status()
    return resp.json()["data"]


def summarize(models, snapshot_date):
    by_id = {m["id"]: m for m in models}
    rows = []
    for model_id in MODEL_BASKET:
        m = by_id.get(model_id)
        if m is None:
            continue
        pricing = m.get("pricing", {})
        rows.append(
            {
                "model_id": model_id,
                "prompt_usd_per_token": pricing.get("prompt"),
                "completion_usd_per_token": pricing.get("completion"),
                "context_length": m.get("context_length"),
                "source": "openrouter_api",
                "snapshot_date": snapshot_date,
            }
        )
    return rows


def pull_llm_pricing(snapshot_date, write=True):
    models = fetch_models()
    rows = summarize(models, snapshot_date)
    if write:
        with open(OUTPUT_PATH, "w", newline="") as f:
            writer = csv.DictWriter(
                f,
                fieldnames=[
                    "model_id",
                    "prompt_usd_per_token",
                    "completion_usd_per_token",
                    "context_length",
                    "source",
                    "snapshot_date",
                ],
            )
            writer.writeheader()
            writer.writerows(rows)
    return rows


if __name__ == "__main__":
    import datetime

    today = datetime.date.today().isoformat()
    for row in pull_llm_pricing(today):
        print(row)
