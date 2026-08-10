from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncEngine

from proxy.app.usage.repository import UsageRepository
from proxy.app.usage.schemas import UsageReport
from proxy.app.usage.service import UsageService
from proxy.database import create_session_factory

router = APIRouter(prefix="/api/servers", tags=["usage"])

DEFAULT_WINDOW = timedelta(hours=1)


def get_usage_service(request: Request) -> UsageService:
    """Build the usage service backed by the gateway's database engine."""

    engine: AsyncEngine = request.app.state.usage_engine
    return UsageService(UsageRepository(create_session_factory(engine)))


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


@router.get("/{name}/usage", response_model=UsageReport)
async def server_usage(
    request: Request,
    name: str,
    from_: Annotated[datetime | None, Query(alias="from")] = None,
    to: datetime | None = None,
    service: UsageService = Depends(get_usage_service),
) -> UsageReport:
    """Return request volumes for a server over a time window."""

    manager = request.app.state.server_manager
    if manager.get(name) is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Unknown MCP server '{name}'.",
        )
    end = _as_utc(to) if to is not None else datetime.now(UTC)
    start = _as_utc(from_) if from_ is not None else end - DEFAULT_WINDOW
    if start >= end:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="'from' must be earlier than 'to'.",
        )
    return await service.report(name, start, end)
