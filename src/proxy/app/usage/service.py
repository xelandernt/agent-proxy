from __future__ import annotations

from collections import Counter
from datetime import datetime, timedelta

from proxy.app.usage.repository import UsageRepository
from proxy.app.usage.schemas import (
    ItemCount,
    SeriesBucket,
    SeriesPoint,
    SeriesReport,
    ServerSeries,
    UsageReport,
)

UNKNOWN_CLIENT: str = "unknown"

BUCKET_STEPS: dict[str, timedelta] = {
    "minute": timedelta(minutes=1),
    "hour": timedelta(hours=1),
    "day": timedelta(days=1),
}


def bucket_count(start: datetime, end: datetime, bucket: str) -> int:
    """Return the number of aligned buckets covering an open time window."""

    first = _floor_bucket(start, bucket)
    span = end - first
    step = BUCKET_STEPS[bucket]
    return max(0, (span + step - timedelta(microseconds=1)) // step)


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

    async def series(
        self,
        server_name: str,
        start: datetime,
        end: datetime,
        bucket: str,
    ) -> SeriesReport:
        rows = await self._repository.series_by_bucket(server_name, start, end, bucket)
        totals: dict[datetime, int] = {}
        tools: dict[datetime, Counter[str]] = {}
        methods: dict[datetime, Counter[str]] = {}
        clients: dict[datetime, Counter[str]] = {}
        statuses: dict[datetime, Counter[str]] = {}
        for bucket_ts, method, item, client_app, status_code, count in rows:
            totals[bucket_ts] = totals.get(bucket_ts, 0) + count
            if method == "tools/call":
                tools.setdefault(bucket_ts, Counter())[item or UNKNOWN_CLIENT] += count
            methods.setdefault(bucket_ts, Counter())[method] += count
            clients.setdefault(bucket_ts, Counter())[client_app or UNKNOWN_CLIENT] += (
                count
            )
            statuses.setdefault(bucket_ts, Counter())[str(status_code)] += count
        return SeriesReport(
            server=server_name,
            start=start,
            end=end,
            bucket=bucket,
            points=[
                SeriesBucket(
                    ts=ts,
                    total=totals.get(ts, 0),
                    tools=_sorted_counts(tools.get(ts)),
                    methods=_sorted_counts(methods.get(ts)),
                    clients=_sorted_counts(clients.get(ts)),
                    statuses=_sorted_counts(statuses.get(ts)),
                )
                for ts in _bucket_times(start, end, bucket)
            ],
        )

    async def series_by_server(
        self,
        start: datetime,
        end: datetime,
        bucket: str,
        server_names: list[str],
    ) -> list[ServerSeries]:
        rows = await self._repository.counts_by_server(start, end, bucket)
        by_name: dict[str, dict[datetime, int]] = {}
        for server_name, bucket_ts, count in rows:
            by_name.setdefault(server_name, {})[bucket_ts] = count
        return [
            ServerSeries(
                name=server_name,
                points=[
                    SeriesPoint(ts=ts, total=by_name.get(server_name, {}).get(ts, 0))
                    for ts in _bucket_times(start, end, bucket)
                ],
            )
            for server_name in server_names
        ]


def _sorted_counts(counts: Counter[str] | None) -> list[ItemCount]:
    if counts is None:
        return []
    ordered = sorted(counts.items(), key=lambda pair: (-pair[1], pair[0]))
    return [ItemCount(name=name, count=count) for name, count in ordered]


def _bucket_times(start: datetime, end: datetime, bucket: str) -> list[datetime]:
    """Bucket boundaries from ``start`` to ``end``, aligned to the bucket unit.

    ``date_trunc`` truncates timestamps to the bucket boundary, so the first
    boundary is ``start`` floored to that unit and the last open bucket ends
    before ``end``.
    """

    step = BUCKET_STEPS[bucket]
    floored = _floor_bucket(start, bucket)
    return [floored + index * step for index in range(bucket_count(start, end, bucket))]


def _floor_bucket(value: datetime, bucket: str) -> datetime:
    floored = value.replace(second=0, microsecond=0)
    if bucket == "hour":
        floored = floored.replace(minute=0)
    elif bucket == "day":
        floored = floored.replace(minute=0, hour=0)
    return floored
