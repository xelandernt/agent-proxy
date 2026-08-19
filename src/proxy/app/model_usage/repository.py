from __future__ import annotations

import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import async_sessionmaker

from proxy.api_keys.models import ApiKeyRecord
from proxy.app.model_usage.models import ModelUsageEvent
from proxy.app.usage.types import UsageBucket
from proxy.app.users.models import UserRecord


@dataclass(frozen=True, slots=True)
class UsageTotals:
    requests: int
    successful_requests: int
    failed_requests: int
    metered_requests: int
    input_tokens: int | None
    output_tokens: int | None
    total_tokens: int | None
    cached_metered_requests: int
    cached_tokens: int | None
    costed_requests: int
    cost_usd: Decimal | None


@dataclass(frozen=True, slots=True)
class ModelUsageFilters:
    start: datetime
    end: datetime
    user_id: uuid.UUID | None = None
    api_key_id: uuid.UUID | None = None
    model: str | None = None


class ModelUsageRepository:
    def __init__(self, session_factory: async_sessionmaker) -> None:
        self._session_factory = session_factory

    async def api_key_belongs_to_user(
        self, api_key_id: uuid.UUID, user_id: uuid.UUID
    ) -> bool:
        statement = select(
            select(ApiKeyRecord.id)
            .where(
                ApiKeyRecord.id == api_key_id,
                ApiKeyRecord.user_id == user_id,
            )
            .exists()
        )
        async with self._session_factory() as session:
            return bool((await session.execute(statement)).scalar_one())

    async def totals(self, filters: ModelUsageFilters) -> UsageTotals:
        statement = select(*_aggregate_columns()).select_from(ModelUsageEvent)
        return _totals(await self._one(_filtered(statement, filters)))

    async def by_model(
        self, filters: ModelUsageFilters
    ) -> list[tuple[str, UsageTotals]]:
        statement = (
            select(ModelUsageEvent.model_name, *_aggregate_columns())
            .select_from(ModelUsageEvent)
            .group_by(ModelUsageEvent.model_name)
            .order_by(func.count().desc(), ModelUsageEvent.model_name)
        )
        return [
            (row[0], _totals(row[1:]))
            for row in await self._all(_filtered(statement, filters))
        ]

    async def by_api_key(
        self, filters: ModelUsageFilters
    ) -> list[tuple[uuid.UUID, str, str, bool, UsageTotals]]:
        revoked = ApiKeyRecord.revoked_at.is_not(None)
        statement = (
            select(
                ApiKeyRecord.id,
                ApiKeyRecord.name,
                ApiKeyRecord.prefix,
                revoked,
                *_aggregate_columns(),
            )
            .select_from(ModelUsageEvent)
            .join(ApiKeyRecord, ApiKeyRecord.id == ModelUsageEvent.api_key_id)
            .group_by(
                ApiKeyRecord.id,
                ApiKeyRecord.name,
                ApiKeyRecord.prefix,
                ApiKeyRecord.revoked_at,
            )
            .order_by(func.count().desc(), ApiKeyRecord.id)
        )
        return [
            (row[0], row[1], row[2], row[3], _totals(row[4:]))
            for row in await self._all(_filtered(statement, filters))
        ]

    async def by_user(
        self, filters: ModelUsageFilters
    ) -> list[tuple[uuid.UUID, str | None, str, UsageTotals]]:
        statement = (
            select(
                UserRecord.id,
                UserRecord.display_name,
                UserRecord.email,
                *_aggregate_columns(),
            )
            .select_from(ModelUsageEvent)
            .join(UserRecord, UserRecord.id == ModelUsageEvent.user_id)
            .group_by(UserRecord.id, UserRecord.display_name, UserRecord.email)
            .order_by(func.count().desc(), UserRecord.id)
        )
        return [
            (row[0], row[1], row[2], _totals(row[3:]))
            for row in await self._all(_filtered(statement, filters))
        ]

    async def series(
        self, filters: ModelUsageFilters, bucket: UsageBucket
    ) -> list[tuple[datetime, UsageTotals]]:
        bucket_ts = func.date_trunc(bucket, ModelUsageEvent.ts)
        statement = (
            select(bucket_ts, *_aggregate_columns())
            .select_from(ModelUsageEvent)
            .group_by(bucket_ts)
            .order_by(bucket_ts)
        )
        return [
            (row[0], _totals(row[1:]))
            for row in await self._all(_filtered(statement, filters))
        ]

    async def _one(self, statement: Select[Any]) -> Sequence[Any]:
        async with self._session_factory() as session:
            return (await session.execute(statement)).one()

    async def _all(self, statement: Select[Any]) -> Sequence[Sequence[Any]]:
        async with self._session_factory() as session:
            return (await session.execute(statement)).all()


def _aggregate_columns() -> tuple[Any, ...]:
    success = ModelUsageEvent.status_code.between(200, 399)
    metered = (
        ModelUsageEvent.input_tokens.is_not(None)
        | ModelUsageEvent.output_tokens.is_not(None)
        | ModelUsageEvent.total_tokens.is_not(None)
    )
    return (
        func.count(),
        func.count().filter(success),
        func.count().filter(~success),
        func.count().filter(metered),
        func.sum(ModelUsageEvent.input_tokens),
        func.sum(ModelUsageEvent.output_tokens),
        func.sum(ModelUsageEvent.total_tokens),
        func.count(ModelUsageEvent.cached_tokens),
        func.sum(ModelUsageEvent.cached_tokens),
        func.count(ModelUsageEvent.cost_usd),
        func.sum(ModelUsageEvent.cost_usd),
    )


def _filtered(statement: Select[Any], filters: ModelUsageFilters) -> Select[Any]:
    conditions = [
        ModelUsageEvent.ts >= filters.start,
        ModelUsageEvent.ts < filters.end,
    ]
    if filters.user_id is not None:
        conditions.append(ModelUsageEvent.user_id == filters.user_id)
    if filters.api_key_id is not None:
        conditions.append(ModelUsageEvent.api_key_id == filters.api_key_id)
    if filters.model is not None:
        conditions.append(ModelUsageEvent.model_name == filters.model)
    return statement.where(*conditions)


def _totals(row: Sequence[Any]) -> UsageTotals:
    return UsageTotals(
        requests=row[0],
        successful_requests=row[1],
        failed_requests=row[2],
        metered_requests=row[3],
        input_tokens=row[4],
        output_tokens=row[5],
        total_tokens=row[6],
        cached_metered_requests=row[7],
        cached_tokens=row[8],
        costed_requests=row[9],
        cost_usd=row[10],
    )
