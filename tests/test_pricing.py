import pytest

from assistant.llm import Usage
from assistant.pricing import PRICES, cost_usd, krw, price_for


def test_cost_matches_the_groundwork_request_trace():
    first = Usage(input=1_646, cached=0, cache_write=1_646, output=528, reasoning=500)
    second = Usage(input=4_008, cached=1_646, cache_write=2_362, output=545, reasoning=500)
    assert cost_usd(first, "gpt-5.6-sol") == pytest.approx(0.01879)
    assert cost_usd(second, "gpt-5.6-sol") == pytest.approx(0.0233684)
    assert krw(cost_usd(first, "gpt-5.6-sol")) == 26


def test_flex_is_half_price_and_long_context_costs_more():
    usage = Usage(input=10_000, output=1_000)
    assert cost_usd(usage, "gpt-5.6-sol", "flex") == pytest.approx(cost_usd(usage, "gpt-5.6-sol") / 2)
    big = Usage(input=300_000, output=1_000)
    assert cost_usd(big, "gpt-5.6-sol") == pytest.approx((300_000 * 8 + 1_000 * 30) / 1_000_000)


def test_dated_model_names_use_the_family_price_and_unknown_models_fail():
    assert price_for("gpt-5.6-sol-2026-08-01") == PRICES["gpt-5.6-sol"]
    with pytest.raises(KeyError):
        price_for("gpt-5.6-terra")


def test_usage_adds_up():
    assert Usage(1, 2, 3, 4, 5) + Usage(10, 20, 30, 40, 50) == Usage(11, 22, 33, 44, 55)
    assert sum([Usage(input=1), Usage(input=2)], Usage()) == Usage(input=3)
