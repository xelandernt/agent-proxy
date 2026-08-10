from __future__ import annotations

from datetime import datetime
from typing import TypeVar

from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import async_sessionmaker

from proxy.app.usage.models import UsageEvent

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

    async def _scalar(self, stmt: Select[tuple[int]]) -> int:
        async with self._session_factory() as session:
            return (await session.execute(stmt)).scalar_one()

    async def _rows(
        self,
        stmt: Select[tuple[RowT, int]],
    ) -> list[tuple[RowT, int]]:
        async with self._session_factory() as session:
            return [(row[0], row[1]) for row in (await session.execute(stmt)).all()]
