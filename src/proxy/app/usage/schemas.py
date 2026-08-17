from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel

from proxy.app.usage.types import UsageBucket


class ItemCount(BaseModel):
    """One labeled usage count."""

    name: str
    count: int


class UsageReport(BaseModel):
    """Request volumes for one MCP server over a time window."""

    server: str
    start: datetime
    end: datetime
    total: int
    tools: list[ItemCount]
    methods: list[ItemCount]
    clients: list[ItemCount]
    statuses: list[ItemCount]


class SeriesBucket(BaseModel):
    """One time bucket in a usage series."""

    ts: datetime
    total: int
    tools: list[ItemCount]
    methods: list[ItemCount]
    clients: list[ItemCount]
    statuses: list[ItemCount]


class SeriesReport(BaseModel):
    """Request volumes for one MCP server bucketed over a time window."""

    server: str
    start: datetime
    end: datetime
    bucket: UsageBucket
    points: list[SeriesBucket]


class SeriesPoint(BaseModel):
    """One time bucket's total request count for a server."""

    ts: datetime
    total: int


class ServerSeries(BaseModel):
    """Totals-only request series for one server."""

    name: str
    points: list[SeriesPoint]


class UsageSeriesDocument(BaseModel):
    """Request totals per mounted server over a time window."""

    servers: list[ServerSeries]
