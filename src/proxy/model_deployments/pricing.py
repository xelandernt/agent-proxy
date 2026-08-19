from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Any

import litellm

from proxy.model_deployments.schemas import ModelPricing

PER_MILLION = Decimal(1_000_000)


def discover_model_pricing(upstream_model: str) -> ModelPricing | None:
    """Return LiteLLM's complete base token price set, when available."""

    try:
        model_info = litellm.get_model_info(upstream_model)
    except Exception:  # noqa: BLE001 - LiteLLM's model map is external input.
        return None

    input_price = _per_million(model_info.get("input_cost_per_token"))
    cached_input_price = _per_million(model_info.get("cache_read_input_token_cost"))
    output_price = _per_million(model_info.get("output_cost_per_token"))
    if input_price is None or cached_input_price is None or output_price is None:
        return None
    return ModelPricing(
        input_usd_per_million_tokens=input_price,
        cached_input_usd_per_million_tokens=cached_input_price,
        output_usd_per_million_tokens=output_price,
    )


def _per_million(value: Any) -> Decimal | None:
    if isinstance(value, bool) or not isinstance(value, (int, float, Decimal)):
        return None
    try:
        price = Decimal(str(value))
    except InvalidOperation:
        return None
    if not price.is_finite() or price < 0:
        return None
    return price * PER_MILLION
