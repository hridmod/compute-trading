"""Pull live LLM API token pricing from the OpenRouter public models endpoint.

No API key required for GET /models. We track two baskets as candidate market
$/token proxies for the MLPerf-benchmarked model (Llama-3.1-405B) -- see the
assumption note in README.md for why one basket alone isn't trustworthy here.
Each basket is a single named model, not a multi-model median. An earlier
version of this basket medianed across a model lineage's sequential dated
releases (e.g. deepseek-chat-v3-0324, v3.1, v3.2) -- but those aren't
concurrent competing products, they're the same lineage's price *falling
over time* ($0.000001 -> $0.0000004/token across those three). Medianing
across them accidentally blends in stale, superseded pricing instead of
reading today's actual rate, which biases the "current market rate" upward.
Fixed by using only the latest release per lineage:

- llama_3_1_405b_family -> nousresearch/hermes-4-405b: newest fine-tune of
  the identical 405B dense base model MLPerf benchmarks (the base model
  itself, meta-llama/llama-3.1-405b-instruct, has been delisted from
  OpenRouter). Architecturally the tightest match, but a thin/low-liquidity
  listing -- price may not reflect real competition.
- deepseek_v3_family -> deepseek/deepseek-v3.2: a more heavily-served,
  competitively-priced flagship model, latest release. NOT an architecture
  match -- DeepSeek-V3 is a ~671B-parameter MoE with ~37B active params per
  token, so it's fundamentally cheaper to serve than a 405B *dense* model
  regardless of market competition. Useful as a liquid reference point, not
  a clean substitute.
"""
import csv
from pathlib import Path

import requests

OPENROUTER_URL = "https://openrouter.ai/api/v1/models"

# Fixed, explicit baskets -- one model each, not fuzzy-matched -- so they're auditable.
MODEL_BASKETS = {
    "llama_3_1_405b_family": "nousresearch/hermes-4-405b",
    "deepseek_v3_family": "deepseek/deepseek-v3.2",
}

OUTPUT_PATH = Path(__file__).resolve().parent.parent / "data" / "llm_pricing.csv"


def fetch_models():
    resp = requests.get(OPENROUTER_URL, timeout=20)
    resp.raise_for_status()
    return resp.json()["data"]


def summarize(models, snapshot_date):
    by_id = {m["id"]: m for m in models}
    rows = []
    for basket, model_id in MODEL_BASKETS.items():
        m = by_id.get(model_id)
        if m is None:
            continue
        pricing = m.get("pricing", {})
        rows.append(
            {
                "basket": basket,
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
                    "basket",
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
