from __future__ import annotations

from proxy.model_deployments.repository import (
    ModelDeploymentNotFound,
    ModelDeploymentRepository,
)
from proxy.model_deployments.schemas import (
    ModelDeploymentCreate,
    ModelDeploymentUpdate,
    ModelDeploymentView,
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
        return [self._view(row) for row in await self._repository.list_all()]

    async def get(self, name: str) -> ModelDeploymentView:
        return self._view(await self._require(name))

    async def resolve(self, name: str) -> ResolvedModelDeployment:
        row = await self._require(name)
        upstream_model, api_base, settings, secrets = await self._providers.resolve(
            row.provider, row.model_id
        )
        return ResolvedModelDeployment(
            name=row.name,
            upstream_model=upstream_model,
            api_base=api_base,
            settings=settings,
            secrets=secrets,
        )

    async def create(self, payload: ModelDeploymentCreate) -> ModelDeploymentView:
        await self._providers.get(payload.provider)
        return self._view(
            await self._repository.create(
                name=payload.name, provider=payload.provider, model_id=payload.model_id
            )
        )

    async def update(
        self, name: str, payload: ModelDeploymentUpdate
    ) -> ModelDeploymentView:
        current = await self._require(name)
        provider = payload.provider or current.provider
        await self._providers.get(provider)
        return self._view(
            await self._repository.update(
                name, provider=provider, model_id=payload.model_id or current.model_id
            )
        )

    async def delete(self, name: str) -> None:
        await self._repository.delete(name)

    async def _require(self, name: str):
        row = await self._repository.get(name)
        if row is None:
            raise ModelDeploymentNotFound(f"Unknown model '{name}'.")
        return row

    @staticmethod
    def _view(row) -> ModelDeploymentView:
        return ModelDeploymentView.model_validate(row)
