from __future__ import annotations

from datetime import datetime
from typing import TypeVar

from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import async_sessionmaker

from proxy.app.usage.models import UsageEvent
from proxy.app.usage.types import UsageBucket

RowT = TypeVar("RowT")


class UsageRepository:
    """Persistence queries over usage events."""

    def __init__(
        self,
        session_factory: async_sessionmaker,
    ) -> None:
        self._session_factory = session_factory

    async def count_total(
        self,
        server_name: str,
        start: datetime,
        end: datetime,
    ) -> int:
        stmt: Select[tuple[int]] = (
            select(func.count())
            .select_from(UsageEvent)
            .where(
                UsageEvent.server_name == server_name,
                UsageEvent.ts >= start,
                UsageEvent.ts < end,
            )
        )
        return await self._scalar(stmt)

    async def counts_by_tool(
        self,
        server_name: str,
        start: datetime,
        end: datetime,
    ) -> list[tuple[str | None, int]]:
        stmt: Select[tuple[str | None, int]] = (
            select(UsageEvent.item, func.count())
            .where(
                UsageEvent.server_name == server_name,
                UsageEvent.method == "tools/call",
                UsageEvent.ts >= start,
                UsageEvent.ts < end,
            )
            .group_by(UsageEvent.item)
            .order_by(func.count().desc())
        )
        return await self._rows(stmt)

    async def counts_by_method(
        self,
        server_name: str,
        start: datetime,
        end: datetime,
    ) -> list[tuple[str, int]]:
        stmt: Select[tuple[str, int]] = (
            select(UsageEvent.method, func.count())
            .where(
                UsageEvent.server_name == server_name,
                UsageEvent.ts >= start,
                UsageEvent.ts < end,
            )
            .group_by(UsageEvent.method)
            .order_by(func.count().desc())
        )
        return await self._rows(stmt)

    async def counts_by_client(
        self,
        server_name: str,
        start: datetime,
        end: datetime,
    ) -> list[tuple[str | None, int]]:
        stmt: Select[tuple[str | None, int]] = (
            select(UsageEvent.client_app, func.count())
            .where(
                UsageEvent.server_name == server_name,
                UsageEvent.ts >= start,
                UsageEvent.ts < end,
            )
            .group_by(UsageEvent.client_app)
            .order_by(func.count().desc())
        )
        return await self._rows(stmt)

    async def counts_by_status(
        self,
        server_name: str,
        start: datetime,
        end: datetime,
    ) -> list[tuple[int, int]]:
        stmt: Select[tuple[int, int]] = (
            select(UsageEvent.status_code, func.count())
            .where(
                UsageEvent.server_name == server_name,
                UsageEvent.ts >= start,
                UsageEvent.ts < end,
            )
            .group_by(UsageEvent.status_code)
            .order_by(func.count().desc(), UsageEvent.status_code.asc())
        )
        async with self._session_factory() as session:
            return [(row[0], row[1]) for row in (await session.execute(stmt)).all()]

    async def series_by_bucket(
        self,
        server_name: str,
        start: datetime,
        end: datetime,
        bucket: UsageBucket,
    ) -> list[tuple[datetime, str, str | None, str | None, int, int]]:
        """Per-bucket counts grouped by every tracking dimension.

        Returns ``(bucket_ts, method, item, client_app, status_code, count)``
        rows where ``bucket_ts`` is ``ts`` truncated to the bucket unit.
        """

        bucket_ts = func.date_trunc(bucket, UsageEvent.ts)
        stmt = (
            select(
                bucket_ts,
                UsageEvent.method,
                UsageEvent.item,
                UsageEvent.client_app,
                UsageEvent.status_code,
                func.count(),
            )
            .where(
                UsageEvent.server_name == server_name,
                UsageEvent.ts >= start,
                UsageEvent.ts < end,
            )
            .group_by(
                bucket_ts,
                UsageEvent.method,
                UsageEvent.item,
                UsageEvent.client_app,
                UsageEvent.status_code,
            )
            .order_by(bucket_ts)
        )
        async with self._session_factory() as session:
            return [
                (row[0], row[1], row[2], row[3], row[4], row[5])
                for row in (await session.execute(stmt)).all()
            ]

    async def counts_by_server(
        self,
        start: datetime,
        end: datetime,
        bucket: UsageBucket,
    ) -> list[tuple[str, datetime, int]]:
        """Per-bucket totals for every server with events in the window.

        Servers without events are absent; callers fill their gaps with zero
        buckets.
        """

        bucket_ts = func.date_trunc(bucket, UsageEvent.ts)
        stmt = (
            select(UsageEvent.server_name, bucket_ts, func.count())
            .where(UsageEvent.ts >= start, UsageEvent.ts < end)
            .group_by(UsageEvent.server_name, bucket_ts)
            .order_by(UsageEvent.server_name, bucket_ts)
        )
        async with self._session_factory() as session:
            return [
                (row[0], row[1], row[2]) for row in (await session.execute(stmt)).all()
            ]

    async def _scalar(self, stmt: Select[tuple[int]]) -> int:
        async with self._session_factory() as session:
            return (await session.execute(stmt)).scalar_one()

    async def _rows(
        self,
        stmt: Select[tuple[RowT, int]],
    ) -> list[tuple[RowT, int]]:
        async with self._session_factory() as session:
            return [(row[0], row[1]) for row in (await session.execute(stmt)).all()]
