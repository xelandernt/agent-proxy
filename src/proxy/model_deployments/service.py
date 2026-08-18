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
from proxy.security.credentials import CredentialCipher


class ModelDeploymentService:
    def __init__(
        self,
        repository: ModelDeploymentRepository,
        cipher: CredentialCipher,
    ) -> None:
        self._repository = repository
        self._cipher = cipher

    async def list(self) -> list[ModelDeploymentView]:
        return [self._view(row) for row in await self._repository.list_all()]

    async def get(self, name: str) -> ModelDeploymentView:
        row = await self._require(name)
        return self._view(row)

    async def resolve(self, name: str) -> ResolvedModelDeployment:
        row = await self._require(name)
        return ResolvedModelDeployment(
            name=row.name,
            upstream_model=row.upstream_model,
            api_base=row.api_base,
            settings=row.settings,
            secrets=self._cipher.decrypt(row.encrypted_secrets),
        )

    async def create(self, payload: ModelDeploymentCreate) -> ModelDeploymentView:
        secrets = {
            name: value.get_secret_value() for name, value in payload.secrets.items()
        }
        row = await self._repository.create(
            name=payload.name,
            description=payload.description,
            upstream_model=payload.upstream_model,
            api_base=str(payload.api_base) if payload.api_base else None,
            settings=payload.settings,
            encrypted_secrets=self._cipher.encrypt(secrets),
            secret_names=sorted(secrets),
        )
        return self._view(row)

    async def update(
        self,
        name: str,
        payload: ModelDeploymentUpdate,
    ) -> ModelDeploymentView:
        current = await self._require(name)
        secrets = self._cipher.decrypt(current.encrypted_secrets)
        for secret_name in payload.remove_secrets:
            secrets.pop(secret_name, None)
        secrets.update(
            {
                secret_name: value.get_secret_value()
                for secret_name, value in payload.set_secrets.items()
            }
        )
        fields_set = payload.model_fields_set
        api_base = current.api_base
        if "api_base" in fields_set:
            api_base = str(payload.api_base) if payload.api_base else None
        row = await self._repository.update(
            name,
            description=(
                payload.description
                if payload.description is not None
                else current.description
            ),
            upstream_model=(
                payload.upstream_model
                if payload.upstream_model is not None
                else current.upstream_model
            ),
            api_base=api_base,
            settings=payload.settings
            if payload.settings is not None
            else current.settings,
            encrypted_secrets=self._cipher.encrypt(secrets),
            secret_names=sorted(secrets),
        )
        return self._view(row)

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
