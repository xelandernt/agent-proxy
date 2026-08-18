from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace
from typing import Any
from uuid import UUID, uuid4

import pytest
from pydantic import ValidationError

from proxy.api_keys.repository import ApiKeyNotFound
from proxy.api_keys.schemas import ApiKeyCreate, ApiKeyUpdate
from proxy.api_keys.service import ApiKeyService

USER_ID = UUID("c8464904-f61b-48e3-9e87-ef0a1e15a05e")


class MemoryApiKeyRepository:
    def __init__(self) -> None:
        self.rows: dict[str, tuple[SimpleNamespace, list[str]]] = {}

    async def list_for_user(
        self, user_id: UUID
    ) -> list[tuple[SimpleNamespace, list[str]]]:
        return [value for value in self.rows.values() if value[0].user_id == user_id]

    async def create(self, **values: Any) -> tuple[SimpleNamespace, list[str]]:
        row = SimpleNamespace(
            id=uuid4(),
            user_id=values["user_id"],
            name=values["name"],
            prefix=values["prefix"],
            digest=values["digest"],
            created_at=datetime.now(UTC),
            last_used_at=None,
            revoked_at=None,
        )
        models = sorted(values["models"])
        self.rows[row.prefix] = (row, models)
        return row, models

    async def update_owned(self, **values: Any) -> tuple[SimpleNamespace, list[str]]:
        for row, models in self.rows.values():
            if row.id == values["key_id"] and row.user_id == values["user_id"]:
                if values["name"] is not None:
                    row.name = values["name"]
                if values["models"] is not None:
                    models[:] = sorted(values["models"])
                return row, models
        raise ApiKeyNotFound("Unknown API key.")

    async def revoke_owned(self, key_id: UUID, user_id: UUID) -> None:
        for row, models in self.rows.values():
            if row.id == key_id and row.user_id == user_id:
                row.revoked_at = datetime.now(UTC)
                models.clear()
                return
        raise ApiKeyNotFound("Unknown API key.")

    async def get_by_prefix(
        self, prefix: str
    ) -> tuple[SimpleNamespace, list[str]] | None:
        return self.rows.get(prefix)

    async def mark_used(self, key_id: UUID) -> None:
        for row, _ in self.rows.values():
            if row.id == key_id:
                row.last_used_at = datetime.now(UTC)


def service() -> tuple[ApiKeyService, MemoryApiKeyRepository]:
    repository = MemoryApiKeyRepository()
    return ApiKeyService(repository), repository  # type: ignore[arg-type]


def test_api_key_scope_requires_unique_nonempty_model_names() -> None:
    with pytest.raises(ValidationError):
        ApiKeyCreate(name="client", models=[])
    with pytest.raises(ValidationError, match="duplicates"):
        ApiKeyCreate(name="client", models=["alpha", "alpha"])
    with pytest.raises(ValidationError, match="invalid model name"):
        ApiKeyCreate(name="client", models=["spaces are invalid"])


@pytest.mark.asyncio
async def test_api_key_is_returned_once_and_stored_as_digest() -> None:
    keys, repository = service()

    created = await keys.create(
        USER_ID,
        ApiKeyCreate(name="agent", models=["model-b", "model-a"]),
    )

    assert created.key.startswith(f"ap_{created.prefix}_")
    row, models = repository.rows[created.prefix]
    assert created.key != row.digest
    assert created.key not in row.digest
    assert len(row.digest) == 64
    assert models == ["model-a", "model-b"]
    assert await keys.authenticate(created.key) is not None
    assert await keys.authenticate(created.key + "wrong") is None


@pytest.mark.asyncio
async def test_api_key_scope_update_and_revocation() -> None:
    keys, _ = service()
    created = await keys.create(USER_ID, ApiKeyCreate(name="agent", models=["model-a"]))

    updated = await keys.update(
        created.id,
        USER_ID,
        ApiKeyUpdate(name="renamed", models=["model-b"]),
    )
    assert updated.name == "renamed"
    assert updated.models == ["model-b"]

    await keys.revoke(created.id, USER_ID)
    assert await keys.authenticate(created.key) is None
    listed = await keys.list_for_user(USER_ID)
    assert listed[0].revoked_at is not None
    assert listed[0].models == []
