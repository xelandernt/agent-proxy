from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace
from typing import Any

import pytest

from proxy.model_deployments.repository import ModelDeploymentNotFound
from proxy.model_deployments.schemas import ModelDeploymentCreate, ModelDeploymentUpdate
from proxy.model_deployments.service import ModelDeploymentService


class MemoryModelRepository:
    def __init__(self) -> None:
        self.rows: dict[str, SimpleNamespace] = {}

    async def list_all(self) -> list[SimpleNamespace]:
        return [self.rows[name] for name in sorted(self.rows)]

    async def get(self, name: str) -> SimpleNamespace | None:
        return self.rows.get(name)

    async def create(self, **values: Any) -> SimpleNamespace:
        now = datetime.now(UTC)
        row = SimpleNamespace(**values, created_at=now, updated_at=now)
        self.rows[row.name] = row
        return row

    async def update(self, name: str, **values: Any) -> SimpleNamespace:
        row = self.rows.get(name)
        if row is None:
            raise ModelDeploymentNotFound(name)
        for key, value in values.items():
            setattr(row, key, value)
        row.updated_at = datetime.now(UTC)
        return row

    async def delete(self, name: str) -> None:
        if self.rows.pop(name, None) is None:
            raise ModelDeploymentNotFound(name)


class MemoryProviders:
    def __init__(self) -> None:
        self.names = {"production"}

    async def get(self, name: str) -> object:
        if name not in self.names:
            raise KeyError(name)
        return object()

    async def resolve(self, name: str, model_id: str):
        assert name == "production"
        return f"openai/{model_id}", None, {}, {"api_key": "secret"}


@pytest.mark.asyncio
async def test_model_contains_only_provider_and_model_id() -> None:
    repository = MemoryModelRepository()
    service = ModelDeploymentService(repository, MemoryProviders())  # type: ignore[arg-type]

    created = await service.create(
        ModelDeploymentCreate(
            name="support-agent", provider="production", model_id="gpt-5"
        )
    )
    resolved = await service.resolve("support-agent")

    assert created.model_dump(exclude={"created_at", "updated_at"}) == {
        "name": "support-agent",
        "provider": "production",
        "model_id": "gpt-5",
    }
    assert resolved.upstream_model == "openai/gpt-5"
    assert resolved.secrets == {"api_key": "secret"}


@pytest.mark.asyncio
async def test_model_update_preserves_unspecified_fields() -> None:
    repository = MemoryModelRepository()
    service = ModelDeploymentService(repository, MemoryProviders())  # type: ignore[arg-type]
    await service.create(
        ModelDeploymentCreate(
            name="support-agent", provider="production", model_id="gpt-5"
        )
    )

    updated = await service.update(
        "support-agent", ModelDeploymentUpdate(model_id="gpt-5-mini")
    )

    assert updated.provider == "production"
    assert updated.model_id == "gpt-5-mini"
