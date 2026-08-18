from __future__ import annotations

import hashlib
import hmac
import secrets
import uuid
from typing import Any

from proxy.api_keys.repository import ApiKeyPrefixCollision, ApiKeyRepository
from proxy.api_keys.schemas import (
    ApiKeyCreate,
    ApiKeyCreated,
    ApiKeyUpdate,
    ApiKeyView,
    AuthenticatedApiKey,
)


class ApiKeyService:
    def __init__(self, repository: ApiKeyRepository) -> None:
        self._repository = repository

    async def list_for_user(self, user_id: uuid.UUID) -> list[ApiKeyView]:
        return [
            _view(row, models)
            for row, models in await self._repository.list_for_user(user_id)
        ]

    async def create(
        self,
        user_id: uuid.UUID,
        payload: ApiKeyCreate,
    ) -> ApiKeyCreated:
        for _ in range(3):
            prefix = secrets.token_hex(4)
            plaintext = f"ap_{prefix}_{secrets.token_urlsafe(32)}"
            try:
                row, models = await self._repository.create(
                    user_id=user_id,
                    name=payload.name,
                    prefix=prefix,
                    digest=_digest(plaintext),
                    models=payload.models,
                )
            except ApiKeyPrefixCollision:
                continue
            return ApiKeyCreated(**_view(row, models).model_dump(), key=plaintext)
        raise RuntimeError("Could not allocate a unique API key prefix.")

    async def update(
        self,
        key_id: uuid.UUID,
        user_id: uuid.UUID,
        payload: ApiKeyUpdate,
    ) -> ApiKeyView:
        row, models = await self._repository.update_owned(
            key_id=key_id,
            user_id=user_id,
            name=payload.name,
            models=payload.models,
        )
        return _view(row, models)

    async def revoke(self, key_id: uuid.UUID, user_id: uuid.UUID) -> None:
        await self._repository.revoke_owned(key_id, user_id)

    async def authenticate(self, plaintext: str) -> AuthenticatedApiKey | None:
        prefix = _parse_prefix(plaintext)
        if prefix is None:
            return None
        found = await self._repository.get_by_prefix(prefix)
        if found is None:
            return None
        row, models = found
        if row.revoked_at is not None or not hmac.compare_digest(
            row.digest, _digest(plaintext)
        ):
            return None
        return AuthenticatedApiKey(
            id=row.id,
            user_id=row.user_id,
            models=frozenset(models),
        )

    async def mark_used(self, key_id: uuid.UUID) -> None:
        await self._repository.mark_used(key_id)


def _digest(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def _parse_prefix(value: str) -> str | None:
    kind, separator, remainder = value.partition("_")
    prefix, second_separator, secret = remainder.partition("_")
    if kind != "ap" or not separator or not second_separator or not secret:
        return None
    if len(prefix) != 8:
        return None
    return prefix


def _view(row: Any, models: list[str]) -> ApiKeyView:
    return ApiKeyView(
        id=row.id,
        name=row.name,
        prefix=row.prefix,
        models=models,
        created_at=row.created_at,
        last_used_at=row.last_used_at,
        revoked_at=row.revoked_at,
    )
