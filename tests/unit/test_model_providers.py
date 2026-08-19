from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace
from typing import Any

import pytest
from cryptography.fernet import Fernet
from pydantic import SecretStr

from proxy.model_providers.repository import ModelProviderNotFound
from proxy.model_providers.schemas import ModelProviderCreate, ModelProviderUpdate
from proxy.model_providers.service import (
    ModelProviderCredentialsMissing,
    ModelProviderService,
)
from proxy.security.credentials import CredentialCipher


class MemoryProviderRepository:
    def __init__(self) -> None:
        self.rows: dict[str, SimpleNamespace] = {}

    async def list_all(self) -> list[SimpleNamespace]:
        return list(self.rows.values())

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
            raise ModelProviderNotFound(name)
        for key, value in values.items():
            setattr(row, key, value)
        row.updated_at = datetime.now(UTC)
        return row


def service() -> tuple[ModelProviderService, MemoryProviderRepository]:
    repository = MemoryProviderRepository()
    cipher = CredentialCipher(SecretStr(Fernet.generate_key().decode()))
    return ModelProviderService(repository, cipher), repository  # type: ignore[arg-type]


@pytest.mark.asyncio
async def test_provider_requires_credentials_and_never_returns_them() -> None:
    providers, repository = service()
    with pytest.raises(ModelProviderCredentialsMissing, match="api_key"):
        await providers.create(
            ModelProviderCreate(name="openai", config={"provider": "openai"})
        )

    view = await providers.create(
        ModelProviderCreate(
            name="openai",
            config={"provider": "openai", "api_key": "top-secret"},
        )
    )

    assert view.config.model_dump(exclude_none=True) == {"provider": "openai"}
    assert view.credential_names == ["api_key"]
    assert "top-secret" not in repository.rows["openai"].encrypted_credentials


@pytest.mark.asyncio
async def test_bedrock_supports_default_api_key_and_access_keys() -> None:
    providers, _ = service()
    await providers.create(
        ModelProviderCreate(
            name="role",
            config={
                "provider": "bedrock",
                "region": "eu-central-1",
                "credentials": {"type": "default"},
            },
        )
    )
    await providers.create(
        ModelProviderCreate(
            name="bearer",
            config={
                "provider": "bedrock",
                "region": "eu-central-1",
                "credentials": {"type": "api_key", "api_key": "key"},
            },
        )
    )
    await providers.create(
        ModelProviderCreate(
            name="keys",
            config={
                "provider": "bedrock",
                "region": "eu-central-1",
                "credentials": {
                    "type": "access_keys",
                    "access_key_id": "id",
                    "secret_access_key": "secret",
                    "session_token": "session",
                },
            },
        )
    )

    role = await providers.resolve("role", "anthropic.claude")
    bearer = await providers.resolve("bearer", "anthropic.claude")
    keys = await providers.resolve("keys", "anthropic.claude")

    assert role == (
        "bedrock/anthropic.claude",
        None,
        {"aws_region_name": "eu-central-1"},
        {},
    )
    assert bearer[3] == {"api_key": "key"}
    assert keys[3] == {
        "aws_access_key_id": "id",
        "aws_secret_access_key": "secret",
        "aws_session_token": "session",
    }


@pytest.mark.asyncio
async def test_update_preserves_omitted_credentials_in_same_mode() -> None:
    providers, _ = service()
    await providers.create(
        ModelProviderCreate(
            name="azure",
            config={
                "provider": "azure_openai",
                "endpoint": "https://example.openai.azure.com",
                "api_version": "2026-01-01",
                "api_key": "secret",
            },
        )
    )

    await providers.update(
        "azure",
        ModelProviderUpdate(
            config={
                "provider": "azure_openai",
                "endpoint": "https://new.openai.azure.com",
                "api_version": "2026-06-01",
            }
        ),
    )

    resolved = await providers.resolve("azure", "deployment")
    assert resolved == (
        "azure/deployment",
        "https://new.openai.azure.com/",
        {"api_version": "2026-06-01"},
        {"api_key": "secret"},
    )


@pytest.mark.asyncio
async def test_openai_compatible_provider_uses_openai_transport() -> None:
    providers, _ = service()
    await providers.create(
        ModelProviderCreate(
            name="compatible",
            config={
                "provider": "openai_compatible",
                "base_url": "https://api.deepseek.com",
                "api_key": "secret",
            },
        )
    )

    resolved = await providers.resolve("compatible", "deepseek-v4-flash")

    assert resolved[0] == "openai/deepseek-v4-flash"
    assert resolved[1] == "https://api.deepseek.com/"
