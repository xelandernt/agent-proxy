from __future__ import annotations

from decimal import Decimal

from proxy.model_deployments.pricing import discover_model_pricing
from proxy.model_deployments.repository import (
    ModelDeploymentNotFound,
    ModelDeploymentRepository,
)
from proxy.model_deployments.schemas import (
    ModelDeploymentCreate,
    ModelDeploymentUpdate,
    ModelDeploymentView,
    ModelPricing,
    ModelPricingView,
    ResolvedModelDeployment,
)
from proxy.model_providers.service import ModelProviderService


class ModelDeploymentService:
    def __init__(
        self, repository: ModelDeploymentRepository, providers: ModelProviderService
    ) -> None:
        self._repository = repository
        self._providers = providers

    async def list(self) -> list[ModelDeploymentView]:
        rows = await self._repository.list_all()
        upstream_models = await self._providers.upstream_models(
            [(row.provider, row.model_id) for row in rows]
        )
        return [
            self._view(row, upstream_model)
            for row, upstream_model in zip(rows, upstream_models, strict=True)
        ]

    async def get(self, name: str) -> ModelDeploymentView:
        row = await self._require(name)
        upstream_model = await self._providers.upstream_model(
            row.provider, row.model_id
        )
        return self._view(row, upstream_model)

    async def resolve(self, name: str) -> ResolvedModelDeployment:
        row = await self._require(name)
        upstream_model, api_base, settings, secrets = await self._providers.resolve(
            row.provider, row.model_id
        )
        pricing = self._custom_pricing(row)
        is_custom = pricing is not None
        pricing = pricing or discover_model_pricing(upstream_model)
        return ResolvedModelDeployment(
            name=row.name,
            upstream_model=upstream_model,
            api_base=api_base,
            settings=settings,
            secrets=secrets,
            pricing=self._pricing_view(pricing, is_custom=is_custom),
        )

    async def create(self, payload: ModelDeploymentCreate) -> ModelDeploymentView:
        await self._providers.get(payload.provider)
        input_price, cached_input_price, output_price = self._pricing_values(
            payload.pricing
        )
        row = await self._repository.create(
            name=payload.name,
            provider=payload.provider,
            model_id=payload.model_id,
            input_usd_per_million_tokens=input_price,
            cached_input_usd_per_million_tokens=cached_input_price,
            output_usd_per_million_tokens=output_price,
        )
        upstream_model = await self._providers.upstream_model(
            row.provider, row.model_id
        )
        return self._view(row, upstream_model)

    async def update(
        self, name: str, payload: ModelDeploymentUpdate
    ) -> ModelDeploymentView:
        current = await self._require(name)
        provider = payload.provider or current.provider
        await self._providers.get(provider)
        pricing = (
            payload.pricing
            if "pricing" in payload.model_fields_set
            else self._custom_pricing(current)
        )
        input_price, cached_input_price, output_price = self._pricing_values(pricing)
        row = await self._repository.update(
            name,
            provider=provider,
            model_id=payload.model_id or current.model_id,
            input_usd_per_million_tokens=input_price,
            cached_input_usd_per_million_tokens=cached_input_price,
            output_usd_per_million_tokens=output_price,
        )
        upstream_model = await self._providers.upstream_model(
            row.provider, row.model_id
        )
        return self._view(row, upstream_model)

    async def delete(self, name: str) -> None:
        await self._repository.delete(name)

    async def _require(self, name: str):
        row = await self._repository.get(name)
        if row is None:
            raise ModelDeploymentNotFound(f"Unknown model '{name}'.")
        return row

    def _view(self, row, upstream_model: str) -> ModelDeploymentView:
        pricing = self._custom_pricing(row)
        is_custom = pricing is not None
        if pricing is None:
            pricing = discover_model_pricing(upstream_model)
        return ModelDeploymentView(
            name=row.name,
            provider=row.provider,
            model_id=row.model_id,
            pricing=self._pricing_view(pricing, is_custom=is_custom),
            created_at=row.created_at,
            updated_at=row.updated_at,
        )

    @staticmethod
    def _custom_pricing(row) -> ModelPricing | None:
        input_price = row.input_usd_per_million_tokens
        if input_price is None:
            return None
        return ModelPricing(
            input_usd_per_million_tokens=input_price,
            cached_input_usd_per_million_tokens=(
                row.cached_input_usd_per_million_tokens
            ),
            output_usd_per_million_tokens=row.output_usd_per_million_tokens,
        )

    @staticmethod
    def _pricing_values(
        pricing: ModelPricing | None,
    ) -> tuple[Decimal | None, Decimal | None, Decimal | None]:
        if pricing is None:
            return None, None, None
        return (
            pricing.input_usd_per_million_tokens,
            pricing.cached_input_usd_per_million_tokens,
            pricing.output_usd_per_million_tokens,
        )

    @staticmethod
    def _pricing_view(
        pricing: ModelPricing | None, *, is_custom: bool
    ) -> ModelPricingView | None:
        if pricing is None:
            return None
        return ModelPricingView(**pricing.model_dump(), is_custom=is_custom)
