from decimal import Decimal

import pytest

from proxy.model_deployments.pricing import discover_model_pricing


def test_discover_model_pricing_requires_a_complete_set(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "proxy.model_deployments.pricing.litellm.get_model_info",
        lambda _model: {
            "input_cost_per_token": 0.000002,
            "cache_read_input_token_cost": None,
            "output_cost_per_token": 0.00001,
        },
    )

    assert discover_model_pricing("openai/private") is None


def test_discover_model_pricing_converts_per_token_rates(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "proxy.model_deployments.pricing.litellm.get_model_info",
        lambda _model: {
            "input_cost_per_token": 0.000002,
            "cache_read_input_token_cost": 0,
            "output_cost_per_token": 0.00001,
        },
    )

    pricing = discover_model_pricing("openai/private")

    assert pricing is not None
    assert pricing.input_usd_per_million_tokens == Decimal("2.000000")
    assert pricing.cached_input_usd_per_million_tokens == Decimal(0)
    assert pricing.output_usd_per_million_tokens == Decimal("10.00000")


def test_discover_model_pricing_ignores_lookup_failures(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail(_model: str) -> object:
        raise RuntimeError("unknown model")

    monkeypatch.setattr("proxy.model_deployments.pricing.litellm.get_model_info", fail)

    assert discover_model_pricing("openai/private") is None
