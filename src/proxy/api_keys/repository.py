from __future__ import annotations

import uuid
from collections.abc import Sequence
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import delete, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from proxy.api_keys.models import ApiKeyModelRecord, ApiKeyRecord
from proxy.model_deployments.models import ModelDeploymentRecord


class ApiKeyNotFound(KeyError):
    pass


class ApiKeyPrefixCollision(ValueError):
    pass


class ApiKeyModelNotFound(ValueError):
    pass


class ApiKeyRepository:
    def __init__(self, session_factory: async_sessionmaker) -> None:
        self._session_factory = session_factory

    async def list_for_user(
        self, user_id: uuid.UUID
    ) -> list[tuple[ApiKeyRecord, list[str]]]:
        async with self._session_factory() as session:
            keys = list(
                (
                    await session.execute(
                        select(ApiKeyRecord)
                        .where(ApiKeyRecord.user_id == user_id)
                        .order_by(ApiKeyRecord.created_at.desc())
                    )
                )
                .scalars()
                .all()
            )
            scopes = await _scopes_by_key(session, [key.id for key in keys])
            return [(key, scopes.get(key.id, [])) for key in keys]

    async def create(
        self,
        *,
        user_id: uuid.UUID,
        name: str,
        prefix: str,
        digest: str,
        models: list[str],
    ) -> tuple[ApiKeyRecord, list[str]]:
        async with self._session_factory() as session:
            await _require_models(session, models)
            row = ApiKeyRecord(
                user_id=user_id,
                name=name,
                prefix=prefix,
                digest=digest,
                created_at=datetime.now(UTC),
                last_used_at=None,
                revoked_at=None,
            )
            session.add(row)
            try:
                await session.flush()
                session.add_all(
                    ApiKeyModelRecord(api_key_id=row.id, model_name=model)
                    for model in models
                )
                await session.commit()
            except IntegrityError as error:
                await session.rollback()
                if "prefix" in str(error).lower():
                    raise ApiKeyPrefixCollision("API key prefix collision.") from error
                raise
            await session.refresh(row)
            return row, sorted(models)

    async def update_owned(
        self,
        *,
        key_id: uuid.UUID,
        user_id: uuid.UUID,
        name: str | None,
        models: list[str] | None,
    ) -> tuple[ApiKeyRecord, list[str]]:
        async with self._session_factory() as session:
            row = await _owned_key(session, key_id, user_id)
            if row is None or row.revoked_at is not None:
                raise ApiKeyNotFound("Unknown API key.")
            if models is not None:
                await _require_models(session, models)
                await session.execute(
                    delete(ApiKeyModelRecord).where(
                        ApiKeyModelRecord.api_key_id == key_id
                    )
                )
                session.add_all(
                    ApiKeyModelRecord(api_key_id=key_id, model_name=model)
                    for model in models
                )
            if name is not None:
                row.name = name
            await session.commit()
            await session.refresh(row)
            current_models = models
            if current_models is None:
                current_models = (await _scopes_by_key(session, [key_id])).get(
                    key_id, []
                )
            return row, sorted(current_models)

    async def revoke_owned(self, key_id: uuid.UUID, user_id: uuid.UUID) -> None:
        async with self._session_factory() as session:
            row = await _owned_key(session, key_id, user_id)
            if row is None:
                raise ApiKeyNotFound("Unknown API key.")
            if row.revoked_at is None:
                row.revoked_at = datetime.now(UTC)
                await session.execute(
                    delete(ApiKeyModelRecord).where(
                        ApiKeyModelRecord.api_key_id == key_id
                    )
                )
                await session.commit()

    async def get_by_prefix(self, prefix: str) -> tuple[ApiKeyRecord, list[str]] | None:
        async with self._session_factory() as session:
            row = (
                await session.execute(
                    select(ApiKeyRecord).where(ApiKeyRecord.prefix == prefix)
                )
            ).scalar_one_or_none()
            if row is None:
                return None
            models = (await _scopes_by_key(session, [row.id])).get(row.id, [])
            return row, models

    async def mark_used(self, key_id: uuid.UUID) -> None:
        async with self._session_factory() as session:
            await session.execute(
                update(ApiKeyRecord)
                .where(ApiKeyRecord.id == key_id)
                .values(last_used_at=datetime.now(UTC))
            )
            await session.commit()


async def _owned_key(
    session: AsyncSession, key_id: uuid.UUID, user_id: uuid.UUID
) -> ApiKeyRecord | None:
    return (
        await session.execute(
            select(ApiKeyRecord).where(
                ApiKeyRecord.id == key_id,
                ApiKeyRecord.user_id == user_id,
            )
        )
    ).scalar_one_or_none()


async def _require_models(session: AsyncSession, models: Sequence[str]) -> None:
    existing = set(
        (
            await session.execute(
                select(ModelDeploymentRecord.name).where(
                    ModelDeploymentRecord.name.in_(models)
                )
            )
        )
        .scalars()
        .all()
    )
    missing = sorted(set(models) - existing)
    if missing:
        raise ApiKeyModelNotFound("Unknown models: " + ", ".join(missing))


async def _scopes_by_key(
    session: AsyncSession, key_ids: Sequence[uuid.UUID]
) -> dict[uuid.UUID, list[str]]:
    if not key_ids:
        return {}
    rows: Sequence[Any] = (
        await session.execute(
            select(ApiKeyModelRecord.api_key_id, ApiKeyModelRecord.model_name)
            .where(ApiKeyModelRecord.api_key_id.in_(key_ids))
            .order_by(ApiKeyModelRecord.model_name)
        )
    ).all()
    result: dict[uuid.UUID, list[str]] = {}
    for key_id, model_name in rows:
        result.setdefault(key_id, []).append(model_name)
    return result
