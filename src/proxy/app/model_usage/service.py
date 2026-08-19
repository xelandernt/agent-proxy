from __future__ import annotations

import asyncio
import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from proxy.app.model_usage.repository import (
    ModelUsageFilters,
    ModelUsageRepository,
    UsageTotals,
)
from proxy.app.model_usage.schemas import (
    AdminModelUsageReport,
    ModelUsageAggregate,
    ModelUsageApiKeyBreakdown,
    ModelUsageModelBreakdown,
    ModelUsageSeriesPoint,
    ModelUsageSeriesReport,
    ModelUsageUserBreakdown,
    UserModelUsageReport,
)
from proxy.app.usage.service import BUCKET_STEPS, bucket_count
from proxy.app.usage.types import UsageBucket

MAX_REPORT_RANGE = timedelta(days=366)
MAX_SERIES_BUCKETS = 1_500


class InvalidModelUsageRange(ValueError):
    pass


class ModelUsageApiKeyNotFound(KeyError):
    pass


class ModelUsageService:
    def __init__(self, repository: ModelUsageRepository) -> None:
        self._repository = repository

    async def request_count(self, start: datetime, end: datetime) -> int:
        """Return the aggregate model request count for a time window."""

        return (await self._repository.totals(_filters(start, end))).requests

    async def user_report(
        self,
        user_id: uuid.UUID,
        start: datetime,
        end: datetime,
        *,
        model: str | None = None,
        api_key_id: uuid.UUID | None = None,
    ) -> UserModelUsageReport:
        filters = await self._user_filters(
            user_id, start, end, model=model, api_key_id=api_key_id
        )
        totals, models, keys = await asyncio.gather(
            self._repository.totals(filters),
            self._repository.by_model(filters),
            self._repository.by_api_key(filters),
        )
        return _user_report(filters, totals, models, keys)

    async def admin_report(
        self,
        start: datetime,
        end: datetime,
        *,
        user_id: uuid.UUID | None = None,
        model: str | None = None,
        api_key_id: uuid.UUID | None = None,
    ) -> AdminModelUsageReport:
        filters = _filters(
            start,
            end,
            user_id=user_id,
            model=model,
            api_key_id=api_key_id,
        )
        totals, models, keys, users = await asyncio.gather(
            self._repository.totals(filters),
            self._repository.by_model(filters),
            self._repository.by_api_key(filters),
            self._repository.by_user(filters),
        )
        report = _user_report(filters, totals, models, keys)
        return AdminModelUsageReport(
            **report.model_dump(),
            users=[
                ModelUsageUserBreakdown(
                    user_id=row_user_id,
                    display_name=display_name,
                    email=email,
                    **_aggregate(values).model_dump(),
                )
                for row_user_id, display_name, email, values in users
            ],
        )

    async def user_series(
        self,
        user_id: uuid.UUID,
        start: datetime,
        end: datetime,
        bucket: UsageBucket,
        *,
        model: str | None = None,
        api_key_id: uuid.UUID | None = None,
    ) -> ModelUsageSeriesReport:
        filters = await self._user_filters(
            user_id, start, end, model=model, api_key_id=api_key_id
        )
        return await self._series(filters, bucket)

    async def admin_series(
        self,
        start: datetime,
        end: datetime,
        bucket: UsageBucket,
        *,
        user_id: uuid.UUID | None = None,
        model: str | None = None,
        api_key_id: uuid.UUID | None = None,
    ) -> ModelUsageSeriesReport:
        return await self._series(
            _filters(
                start,
                end,
                user_id=user_id,
                model=model,
                api_key_id=api_key_id,
            ),
            bucket,
        )

    async def _user_filters(
        self,
        user_id: uuid.UUID,
        start: datetime,
        end: datetime,
        *,
        model: str | None,
        api_key_id: uuid.UUID | None,
    ) -> ModelUsageFilters:
        if (
            api_key_id is not None
            and not await self._repository.api_key_belongs_to_user(api_key_id, user_id)
        ):
            raise ModelUsageApiKeyNotFound("Unknown API key.")
        return _filters(
            start,
            end,
            user_id=user_id,
            model=model,
            api_key_id=api_key_id,
        )

    async def _series(
        self, filters: ModelUsageFilters, bucket: UsageBucket
    ) -> ModelUsageSeriesReport:
        if bucket_count(filters.start, filters.end, bucket) > MAX_SERIES_BUCKETS:
            raise InvalidModelUsageRange("The requested range has too many buckets.")
        rows = dict(await self._repository.series(filters, bucket))
        return ModelUsageSeriesReport(
            start=filters.start,
            end=filters.end,
            bucket=bucket,
            points=[
                ModelUsageSeriesPoint(
                    ts=ts, **_aggregate(rows.get(ts, _empty())).model_dump()
                )
                for ts in _bucket_times(filters.start, filters.end, bucket)
            ],
        )


def _filters(
    start: datetime,
    end: datetime,
    *,
    user_id: uuid.UUID | None = None,
    model: str | None = None,
    api_key_id: uuid.UUID | None = None,
) -> ModelUsageFilters:
    if start.tzinfo is None or end.tzinfo is None:
        raise InvalidModelUsageRange("'from' and 'to' must include a UTC offset.")
    start = start.astimezone(UTC)
    end = end.astimezone(UTC)
    if start >= end:
        raise InvalidModelUsageRange("'from' must be earlier than 'to'.")
    if end - start > MAX_REPORT_RANGE:
        raise InvalidModelUsageRange("The requested range cannot exceed 366 days.")
    return ModelUsageFilters(start, end, user_id, api_key_id, model)


def _user_report(
    filters: ModelUsageFilters,
    totals: UsageTotals,
    models: list[tuple[str, UsageTotals]],
    keys: list[tuple[uuid.UUID, str, str, bool, UsageTotals]],
) -> UserModelUsageReport:
    return UserModelUsageReport(
        start=filters.start,
        end=filters.end,
        **_aggregate(totals).model_dump(),
        models=[
            ModelUsageModelBreakdown(model=name, **_aggregate(values).model_dump())
            for name, values in models
        ],
        api_keys=[
            ModelUsageApiKeyBreakdown(
                api_key_id=key_id,
                name=name,
                prefix=prefix,
                revoked=revoked,
                **_aggregate(values).model_dump(),
            )
            for key_id, name, prefix, revoked, values in keys
        ],
    )


def _aggregate(values: UsageTotals) -> ModelUsageAggregate:
    return ModelUsageAggregate(
        requests=values.requests,
        successful_requests=values.successful_requests,
        failed_requests=values.failed_requests,
        metered_requests=values.metered_requests,
        input_tokens=values.input_tokens,
        output_tokens=values.output_tokens,
        total_tokens=values.total_tokens,
        cached_metered_requests=values.cached_metered_requests,
        cached_tokens=values.cached_tokens,
        costed_requests=values.costed_requests,
        cost_usd=_decimal_string(values.cost_usd),
    )


def _decimal_string(value: Decimal | None) -> str | None:
    if value is None:
        return None
    decimal_string = format(value, "f").rstrip("0").rstrip(".")
    return decimal_string or "0"


def _empty() -> UsageTotals:
    return UsageTotals(0, 0, 0, 0, None, None, None, 0, None, 0, None)


def _bucket_times(
    start: datetime, end: datetime, bucket: UsageBucket
) -> list[datetime]:
    step = BUCKET_STEPS[bucket]
    current = start.replace(second=0, microsecond=0)
    if bucket == "hour":
        current = current.replace(minute=0)
    elif bucket == "day":
        current = current.replace(minute=0, hour=0)
    return [current + index * step for index in range(bucket_count(start, end, bucket))]
