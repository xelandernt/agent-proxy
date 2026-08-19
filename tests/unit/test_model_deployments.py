from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from types import SimpleNamespace
from typing import Any

import pytest
from pydantic import ValidationError

from proxy.model_deployments.repository import ModelDeploymentNotFound
from proxy.model_deployments.schemas import (
    ModelDeploymentCreate,
    ModelDeploymentUpdate,
    ModelPricing,
)
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

    async def upstream_model(self, name: str, model_id: str) -> str:
        assert name == "production"
        return f"openai/{model_id}"

    async def upstream_models(self, deployments: list[tuple[str, str]]) -> list[str]:
        return [
            await self.upstream_model(name, model_id) for name, model_id in deployments
        ]


def pricing() -> ModelPricing:
    return ModelPricing(
        input_usd_per_million_tokens=Decimal(2),
        cached_input_usd_per_million_tokens=Decimal("0.5"),
        output_usd_per_million_tokens=Decimal(10),
    )


@pytest.mark.asyncio
async def test_model_resolves_custom_pricing() -> None:
    repository = MemoryModelRepository()
    service = ModelDeploymentService(repository, MemoryProviders())  # type: ignore[arg-type]

    created = await service.create(
        ModelDeploymentCreate(
            name="support-agent",
            provider="production",
            model_id="gpt-5",
            pricing=pricing(),
        )
    )
    resolved = await service.resolve("support-agent")

    assert created.model_dump(exclude={"created_at", "updated_at"}) == {
        "name": "support-agent",
        "provider": "production",
        "model_id": "gpt-5",
        "pricing": {
            "input_usd_per_million_tokens": Decimal(2),
            "cached_input_usd_per_million_tokens": Decimal("0.5"),
            "output_usd_per_million_tokens": Decimal(10),
            "is_custom": True,
        },
    }
    assert resolved.upstream_model == "openai/gpt-5"
    assert resolved.secrets == {"api_key": "secret"}


@pytest.mark.asyncio
async def test_model_update_preserves_unspecified_fields() -> None:
    repository = MemoryModelRepository()
    service = ModelDeploymentService(repository, MemoryProviders())  # type: ignore[arg-type]
    await service.create(
        ModelDeploymentCreate(
            name="support-agent",
            provider="production",
            model_id="gpt-5",
            pricing=pricing(),
        )
    )

    updated = await service.update(
        "support-agent", ModelDeploymentUpdate(model_id="gpt-5-mini")
    )

    assert updated.provider == "production"
    assert updated.model_id == "gpt-5-mini"
    assert updated.pricing is not None
    assert updated.pricing.is_custom is True


@pytest.mark.asyncio
async def test_model_update_removes_custom_pricing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repository = MemoryModelRepository()
    service = ModelDeploymentService(repository, MemoryProviders())  # type: ignore[arg-type]
    monkeypatch.setattr(
        "proxy.model_deployments.service.discover_model_pricing",
        lambda _model: None,
    )
    await service.create(
        ModelDeploymentCreate(
            name="support-agent",
            provider="production",
            model_id="private-model",
            pricing=pricing(),
        )
    )

    updated = await service.update(
        "support-agent", ModelDeploymentUpdate.model_validate({"pricing": None})
    )

    assert updated.pricing is None


@pytest.mark.asyncio
async def test_model_labels_discovered_pricing_as_not_custom(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repository = MemoryModelRepository()
    service = ModelDeploymentService(repository, MemoryProviders())  # type: ignore[arg-type]
    monkeypatch.setattr(
        "proxy.model_deployments.service.discover_model_pricing",
        lambda _model: pricing(),
    )

    created = await service.create(
        ModelDeploymentCreate(
            name="support-agent", provider="production", model_id="gpt-5"
        )
    )

    assert created.pricing is not None
    assert created.pricing.is_custom is False


def test_custom_pricing_requires_all_three_nonnegative_values() -> None:
    with pytest.raises(ValidationError):
        ModelDeploymentCreate.model_validate(
            {
                "name": "support-agent",
                "provider": "production",
                "model_id": "gpt-5",
                "pricing": {"input_usd_per_million_tokens": 1},
            }
        )
    with pytest.raises(ValidationError):
        ModelDeploymentCreate(
            name="support-agent",
            provider="production",
            model_id="gpt-5",
            pricing=ModelPricing(
                input_usd_per_million_tokens=Decimal(-1),
                cached_input_usd_per_million_tokens=Decimal(0),
                output_usd_per_million_tokens=Decimal(0),
            ),
        )


def test_custom_pricing_accepts_an_all_zero_set() -> None:
    zero = ModelPricing(
        input_usd_per_million_tokens=Decimal(0),
        cached_input_usd_per_million_tokens=Decimal(0),
        output_usd_per_million_tokens=Decimal(0),
    )

    assert (
        ModelDeploymentCreate(
            name="free", provider="production", model_id="free", pricing=zero
        ).pricing
        == zero
    )
