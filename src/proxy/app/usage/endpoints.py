from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncEngine

from proxy.app.usage.repository import UsageRepository
from proxy.app.usage.schemas import UsageReport
from proxy.app.usage.service import UsageService
from proxy.app.well_known import get_config
from proxy.database import create_session_factory
from proxy.settings import GatewayConfig

router = APIRouter(prefix="/api/servers", tags=["usage"])

DEFAULT_WINDOW = timedelta(hours=1)


def get_usage_service(request: Request) -> UsageService:
    """Build the usage service, failing clearly when tracing is disabled."""

    engine: AsyncEngine | None = request.app.state.usage_engine
    if engine is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Usage tracing is disabled: no database is configured.",
        )
    return UsageService(UsageRepository(create_session_factory(engine)))


def _server_exists(config: GatewayConfig, name: str) -> bool:
    return any(server.name == name for server in config.servers)


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


@router.get("/{name}/usage", response_model=UsageReport)
async def server_usage(
    name: str,
    from_: Annotated[datetime | None, Query(alias="from")] = None,
    to: datetime | None = None,
    config: GatewayConfig = Depends(get_config),
    service: UsageService = Depends(get_usage_service),
) -> UsageReport:
    """Return request volumes for a server over a time window."""

    if not _server_exists(config, name):
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
