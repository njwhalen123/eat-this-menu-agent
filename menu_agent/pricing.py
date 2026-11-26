"""List prices, USD per million tokens, confirmed on
https://platform.claude.com/docs/en/about-claude/pricing on 2026-11-25.
A run records the table it used, so later price changes don't rewrite results."""
from __future__ import annotations

CONFIRMED_ON = "2026-11-25"

# input, output, 5-minute cache write, cache hit
PRICES = {
    "claude-sonnet-5-5": {"input": 2.00, "output": 10.00, "cache_write": 2.50, "cache_read": 0.10},
    "claude-opus-5-5": {"input": 4.00, "output": 20.00, "cache_write": 5.00, "cache_read": 0.20},
    # Haiku 5.5 has two tiers, by the request's total prompt length (input + cache reads + cache writes)
    "claude-haiku-5-5": {"input": 0.10, "output": 0.50, "cache_write": 0.125, "cache_read": 0.01,
                         "long_threshold": 100_000,
                         "long": {"input": 0.50, "output": 2.50, "cache_write": 0.625, "cache_read": 0.05}},
}


def request_cost(model: str, usage: dict) -> float:
    p = PRICES[model]
    prompt = usage.get("input_tokens", 0) + usage.get("cache_read_input_tokens", 0) + usage.get("cache_creation_input_tokens", 0)
    if "long_threshold" in p and prompt > p["long_threshold"]:
        p = p["long"]
    return (usage.get("input_tokens", 0) * p["input"]
            + usage.get("output_tokens", 0) * p["output"]
            + usage.get("cache_creation_input_tokens", 0) * p["cache_write"]
            + usage.get("cache_read_input_tokens", 0) * p["cache_read"]) / 1_000_000
