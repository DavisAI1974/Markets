"""The price table as data. Each entry says where it was read and when. Dollars per million tokens.

Source of every figure below: the Claude API reference price table, cached 2026-11-03 (the
claude-api skill bundled with Claude Code 2.1.331). Where that table gives no figure the rule used is
named in the entry. A `--prices <file>` argument (load_prices) replaces the whole table.

The cost is the API's price for the tokens. It is a compute cost of the token test; it is not a trade
cost and enters no market calculation.
"""

from __future__ import annotations

import json
from decimal import Decimal as D
from pathlib import Path

SONNET = "claude-sonnet-5-5"
HAIKU = "claude-haiku-5-5"

READ_ON = "2026-11-03"
SOURCE = "Claude API reference price table, cached 2026-11-03"

PRICES = {
    "schema": "markets.token_test.prices.v1",
    "models": {
        SONNET: {
            "tiers": [{"prompt_tokens_up_to": None, "input": "2.00", "output": "10.00", "cache_read": "0.10"}],
            "source": SOURCE, "read_on": READ_ON,
        },
        HAIKU: {
            # prompt = input + cache_creation + cache_read tokens of the one call
            "tiers": [{"prompt_tokens_up_to": 100000, "input": "0.10", "output": "0.50", "cache_read": None},
                      {"prompt_tokens_up_to": None, "input": "0.50", "output": "2.50", "cache_read": None}],
            "source": SOURCE + " (0.10/0.50 for prompts up to 100,000 tokens, 0.50/2.50 beyond)", "read_on": READ_ON,
        },
    },
    "cache_write_multiplier": {"value": "1.25", "note": "default 5-minute lifetime", "source": SOURCE, "read_on": READ_ON},
    "cache_read_multiplier_when_no_figure": {"value": "0.1", "note": "of the input price, used where a tier has no cache_read figure",
                                              "source": SOURCE, "read_on": READ_ON},
    "batch_multiplier": {"value": "0.5", "note": "a batch request costs half", "source": SOURCE, "read_on": READ_ON},
}

USAGE_FIELDS = ("input_tokens", "cache_creation_input_tokens", "cache_read_input_tokens", "output_tokens")


def load_prices(path) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _tier(entry: dict, prompt_tokens: int) -> dict:
    for t in entry["tiers"]:
        up = t["prompt_tokens_up_to"]
        if up is None or prompt_tokens <= up:
            return t
    raise ValueError("price table has no tier for this prompt size")


def cost(model: str, usage: dict, batch: bool = False, prices: dict | None = None) -> dict:
    """The cost of ONE call from its own four usage figures, with the arithmetic shown."""
    table = prices or PRICES
    if model not in table["models"]:
        raise KeyError(f"{model} is not in the price table")
    u = {k: int(usage.get(k) or 0) for k in USAGE_FIELDS}
    prompt = u["input_tokens"] + u["cache_creation_input_tokens"] + u["cache_read_input_tokens"]
    t = _tier(table["models"][model], prompt)
    inp, out = D(t["input"]), D(t["output"])
    read = D(t["cache_read"]) if t.get("cache_read") is not None else inp * D(table["cache_read_multiplier_when_no_figure"]["value"])
    write = inp * D(table["cache_write_multiplier"]["value"])
    M = D(1_000_000)
    parts = [
        ("input_tokens", u["input_tokens"], inp),
        ("cache_creation_input_tokens", u["cache_creation_input_tokens"], write),
        ("cache_read_input_tokens", u["cache_read_input_tokens"], read),
        ("output_tokens", u["output_tokens"], out),
    ]
    lines, total = [], D(0)
    for name, n, rate in parts:
        amount = D(n) * rate / M
        total += amount
        lines.append({"field": name, "tokens": n, "dollars_per_million": str(rate), "dollars": str(amount),
                      "arithmetic": f"{n} x {rate} / 1,000,000 = {amount}"})
    factor = D(table["batch_multiplier"]["value"]) if batch else D(1)
    final = total * factor
    return {"model": model, "batch": batch, "prompt_tokens": prompt, "tier_prompt_tokens_up_to": t["prompt_tokens_up_to"],
            "lines": lines, "subtotal": str(total), "batch_factor": str(factor), "total": float(final), "total_exact": str(final),
            "price_source": table["models"][model].get("source"), "price_read_on": table["models"][model].get("read_on")}
