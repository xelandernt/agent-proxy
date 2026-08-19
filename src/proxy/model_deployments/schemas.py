from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Annotated, Any

from pydantic import BaseModel, ConfigDict, Field

from proxy.servers.constants import NAME_PATTERN

UsdPerMillionTokens = Annotated[
    Decimal,
    Field(ge=0, max_digits=20, decimal_places=12),
]


class ModelPricing(BaseModel):
    """Atomic USD prices for one million tokens."""

    model_config = ConfigDict(extra="forbid")

    input_usd_per_million_tokens: UsdPerMillionTokens
    cached_input_usd_per_million_tokens: UsdPerMillionTokens
    output_usd_per_million_tokens: UsdPerMillionTokens


class ModelPricingView(ModelPricing):
    is_custom: bool


class ModelDeploymentCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(pattern=NAME_PATTERN, max_length=100)
    provider: str = Field(pattern=NAME_PATTERN, max_length=100)
    model_id: str = Field(min_length=1, max_length=255)
    pricing: ModelPricing | None = None


class ModelDeploymentUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    provider: str | None = Field(default=None, pattern=NAME_PATTERN, max_length=100)
    model_id: str | None = Field(default=None, min_length=1, max_length=255)
    pricing: ModelPricing | None = None


class ModelDeploymentView(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    name: str
    provider: str
    model_id: str
    pricing: ModelPricingView | None
    created_at: datetime
    updated_at: datetime


class ResolvedModelDeployment(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    upstream_model: str
    api_base: str | None
    settings: dict[str, Any]
    secrets: dict[str, str]
    pricing: ModelPricingView | None
