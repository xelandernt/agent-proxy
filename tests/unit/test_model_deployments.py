from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace
from typing import Any

import pytest
from cryptography.fernet import Fernet
from pydantic import SecretStr, ValidationError

from proxy.model_deployments.repository import ModelDeploymentNotFound
from proxy.model_deployments.schemas import (
    ModelDeploymentCreate,
    ModelDeploymentUpdate,
)
from proxy.model_deployments.service import ModelDeploymentService
from proxy.security.credentials import CredentialCipher


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
        current = self.rows.get(name)
        if current is None:
            raise ModelDeploymentNotFound(name)
        for key, value in values.items():
            setattr(current, key, value)
        current.updated_at = datetime.now(UTC)
        return current

    async def delete(self, name: str) -> None:
        if self.rows.pop(name, None) is None:
            raise ModelDeploymentNotFound(name)


def service() -> tuple[ModelDeploymentService, MemoryModelRepository, CredentialCipher]:
    repository = MemoryModelRepository()
    cipher = CredentialCipher(SecretStr(Fernet.generate_key().decode()))
    return ModelDeploymentService(repository, cipher), repository, cipher  # type: ignore[arg-type]


def test_model_schema_keeps_secrets_out_of_settings() -> None:
    with pytest.raises(ValidationError, match="belong in secrets"):
        ModelDeploymentCreate(
            name="claude",
            upstream_model="anthropic/claude",
            settings={"api_token": "secret"},
        )

    with pytest.raises(ValidationError, match="reserved"):
        ModelDeploymentCreate(
            name="claude",
            upstream_model="anthropic/claude",
            secrets={"model": "secret"},
        )

    with pytest.raises(ValidationError, match="belong in secrets"):
        ModelDeploymentCreate(
            name="bedrock",
            upstream_model="bedrock/anthropic.claude",
            settings={"aws_access_key_id": "secret"},
        )


def test_model_schema_accepts_representative_provider_arguments() -> None:
    bedrock = ModelDeploymentCreate(
        name="bedrock",
        upstream_model="bedrock/anthropic.claude-v2",
        settings={"aws_region_name": "eu-central-1"},
        secrets={
            "aws_access_key_id": "access-key",
            "aws_secret_access_key": "secret-key",
        },
    )
    azure = ModelDeploymentCreate(
        name="azure",
        upstream_model="azure/gpt-5",
        api_base="https://example.openai.azure.com",
        settings={"api_version": "2026-06-01"},
        secrets={"api_key": "azure-key"},
    )

    assert bedrock.settings["aws_region_name"] == "eu-central-1"
    assert azure.api_base is not None


@pytest.mark.asyncio
async def test_model_service_encrypts_and_explicitly_updates_secrets() -> None:
    models, repository, cipher = service()

    created = await models.create(
        ModelDeploymentCreate(
            name="claude",
            description="Coding model",
            upstream_model="anthropic/claude-sonnet",
            settings={"timeout": 30},
            secrets={"anthropic_api_key": "first", "region_token": "second"},
        )
    )

    stored = repository.rows["claude"]
    assert "first" not in stored.encrypted_secrets
    assert created.secret_names == ["anthropic_api_key", "region_token"]
    assert not hasattr(created, "secrets")

    updated = await models.update(
        "claude",
        ModelDeploymentUpdate(
            set_secrets={"anthropic_api_key": "replacement"},
            remove_secrets=["region_token"],
        ),
    )

    assert updated.secret_names == ["anthropic_api_key"]
    assert cipher.decrypt(stored.encrypted_secrets) == {
        "anthropic_api_key": "replacement"
    }
    resolved = await models.resolve("claude")
    assert resolved.name == "claude"
    assert resolved.upstream_model == "anthropic/claude-sonnet"
    assert resolved.secrets == {"anthropic_api_key": "replacement"}


@pytest.mark.asyncio
async def test_model_service_preserves_or_clears_api_base_explicitly() -> None:
    models, _, _ = service()
    await models.create(
        ModelDeploymentCreate(
            name="azure",
            upstream_model="azure/deployment",
            api_base="https://azure.example.com",
        )
    )

    preserved = await models.update("azure", ModelDeploymentUpdate(description="New"))
    cleared = await models.update("azure", ModelDeploymentUpdate(api_base=None))

    assert preserved.api_base == "https://azure.example.com/"
    assert cleared.api_base is None
