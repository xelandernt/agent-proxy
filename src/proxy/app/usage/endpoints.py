from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncEngine

from proxy.app.usage.repository import UsageRepository
from proxy.app.usage.schemas import SeriesReport, UsageReport, UsageSeriesDocument
from proxy.app.usage.service import UsageService, bucket_count
from proxy.database import create_session_factory

router = APIRouter(prefix="/api/servers", tags=["usage"])

DEFAULT_WINDOW = timedelta(hours=1)
SPARKLINE_WINDOW = timedelta(hours=24)
VALID_BUCKETS = frozenset({"minute", "hour", "day"})
MAX_USAGE_WINDOW = timedelta(days=366)
MAX_SERIES_POINTS = 1500


def get_usage_service(request: Request) -> UsageService:
    """Build the usage service backed by the gateway's database engine."""

    engine: AsyncEngine = request.app.state.usage_engine
    return UsageService(UsageRepository(create_session_factory(engine)))


UsageServiceDependency = Annotated[UsageService, Depends(get_usage_service)]


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _bucket_for_window(start: datetime, end: datetime) -> str:
    window = end - start
    if window <= timedelta(hours=6):
        return "minute"
    if window <= timedelta(days=7):
        return "hour"
    return "day"


def _resolve_bucket(start: datetime, end: datetime, bucket: str | None) -> str:
    resolved = bucket or _bucket_for_window(start, end)
    if resolved not in VALID_BUCKETS:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=f"Invalid bucket '{resolved}'; expected one of "
            f"{sorted(VALID_BUCKETS)}.",
        )
    points = bucket_count(start, end, resolved)
    if points > MAX_SERIES_POINTS:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=(
                f"Requested series contains {points} points; the maximum is "
                f"{MAX_SERIES_POINTS}. Use a larger bucket or shorter window."
            ),
        )
    return resolved


def _window(
    from_: datetime | None,
    to: datetime | None,
    default: timedelta = DEFAULT_WINDOW,
) -> tuple[datetime, datetime]:
    end = _as_utc(to) if to is not None else datetime.now(UTC)
    start = _as_utc(from_) if from_ is not None else end - default
    if start >= end:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="'from' must be earlier than 'to'.",
        )
    if end - start > MAX_USAGE_WINDOW:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=f"Usage windows cannot exceed {MAX_USAGE_WINDOW.days} days.",
        )
    return start, end


def _require_server(request: Request, name: str) -> None:
    manager = request.app.state.server_manager
    if manager.get(name) is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Unknown MCP server '{name}'.",
        )


@router.get("/series", response_model=UsageSeriesDocument)
async def servers_usage_series(
    request: Request,
    service: UsageServiceDependency,
    from_: Annotated[datetime | None, Query(alias="from")] = None,
    to: datetime | None = None,
    bucket: str | None = None,
) -> UsageSeriesDocument:
    """Return request totals per server over a time window."""

    start, end = _window(from_, to, SPARKLINE_WINDOW)
    resolved = _resolve_bucket(start, end, bucket)
    manager = request.app.state.server_manager
    names = [server.name for server in manager.snapshot()]
    return UsageSeriesDocument(
        servers=await service.series_by_server(start, end, resolved, names)
    )


@router.get("/{name}/usage", response_model=UsageReport)
async def server_usage(
    request: Request,
    name: str,
    service: UsageServiceDependency,
    from_: Annotated[datetime | None, Query(alias="from")] = None,
    to: datetime | None = None,
) -> UsageReport:
    """Return request volumes for a server over a time window."""

    _require_server(request, name)
    start, end = _window(from_, to)
    return await service.report(name, start, end)


@router.get("/{name}/usage/series", response_model=SeriesReport)
async def server_usage_series(
    request: Request,
    name: str,
    service: UsageServiceDependency,
    from_: Annotated[datetime | None, Query(alias="from")] = None,
    to: datetime | None = None,
    bucket: str | None = None,
) -> SeriesReport:
    """Return bucketed request volumes for a server over a time window."""

    _require_server(request, name)
    start, end = _window(from_, to)
    resolved = _resolve_bucket(start, end, bucket)
    return await service.series(name, start, end, resolved)
