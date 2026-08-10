from __future__ import annotations

from datetime import datetime

from proxy.app.usage.repository import UsageRepository
from proxy.app.usage.schemas import ItemCount, UsageReport

UNKNOWN_CLIENT: str = "unknown"


class UsageService:
    """Build usage reports for a single MCP server."""

    def __init__(self, repository: UsageRepository) -> None:
        self._repository = repository

    async def report(
        self,
        server_name: str,
        start: datetime,
        end: datetime,
    ) -> UsageReport:
        tools, methods, clients, statuses = (
            self._repository.counts_by_tool(server_name, start, end),
            self._repository.counts_by_method(server_name, start, end),
            self._repository.counts_by_client(server_name, start, end),
            self._repository.counts_by_status(server_name, start, end),
        )
        total = await self._repository.count_total(server_name, start, end)
        return UsageReport(
            server=server_name,
            start=start,
            end=end,
            total=total,
            tools=[
                ItemCount(name=name or UNKNOWN_CLIENT, count=count)
                for name, count in await tools
            ],
            methods=[
                ItemCount(name=name, count=count) for name, count in await methods
            ],
            clients=[
                ItemCount(name=name or UNKNOWN_CLIENT, count=count)
                for name, count in await clients
            ],
            statuses=[
                ItemCount(name=str(status), count=count)
                for status, count in await statuses
            ],
        )
