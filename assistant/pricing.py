"""Token prices and cost (spec 6.3, groundwork O10). USD per 1M tokens, Standard tier, short context."""
from __future__ import annotations

from assistant.llm import Usage

USD_TO_KRW = 1400
LONG_CONTEXT_INPUT = 272_000
PRICES = {"gpt-5.6-sol": {"input": 4.00, "cached": 0.40, "cache_write": 5.00, "output": 20.00}}


def price_for(model: str) -> dict[str, float]:
    """Exact name or a dated snapshot of it (gpt-5.6-sol-2026-08-01)."""
    for name, price in PRICES.items():
        if model == name or model.startswith(name + "-"):
            return price
    raise KeyError(f"가격표에 없는 모델입니다: {model}")


def cost_usd(usage: Usage, model: str, service_tier: str | None = None) -> float:
    """(input - cached - cache_write) x input + cached x cached + cache_write x cache_write + output x output.
    A request above 272K input costs 2x input and 1.5x output. Flex costs half."""
    price = price_for(model)
    ordinary = usage.input - usage.cached - usage.cache_write
    input_cost = ordinary * price["input"] + usage.cached * price["cached"] + usage.cache_write * price["cache_write"]
    output_cost = usage.output * price["output"]
    if usage.input > LONG_CONTEXT_INPUT:
        input_cost, output_cost = input_cost * 2, output_cost * 1.5
    usd = (input_cost + output_cost) / 1_000_000
    return usd / 2 if service_tier == "flex" else usd


def krw(usd: float) -> int:
    return round(usd * USD_TO_KRW)
