from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


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
