from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import Awaitable, Callable, MutableMapping
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from mcp.types import CLIENT_INFO_META_KEY
from sqlalchemy.ext.asyncio import async_sessionmaker

from proxy.app.usage.models import UsageEvent

logger = logging.getLogger(__name__)

Scope = MutableMapping[str, Any]
Message = MutableMapping[str, Any]
Receive = Callable[[], Awaitable[Message]]
Send = Callable[[Message], Awaitable[None]]
ASGIApp = Callable[[Scope, Receive, Send], Awaitable[None]]

MAX_REQUEST_BODY_BYTES = 1024 * 1024
USAGE_QUEUE_SIZE = 4096
USAGE_BATCH_SIZE = 100
METHOD_MAX_LENGTH = 64
ITEM_MAX_LENGTH = 255
CLIENT_APP_MAX_LENGTH = 128


@dataclass(frozen=True, slots=True)
class UsageEventData:
    """One trackable JSON-RPC request, extracted from the wire payload."""

    method: str
    item: str | None
    client_app: str | None


@dataclass(frozen=True, slots=True)
class UsageRecord:
    """One response outcome waiting to be persisted by the usage worker."""

    server_name: str
    method: str
    item: str | None
    client_app: str | None
    status_code: int
    ts: datetime


def extract_usage_event(payload: bytes) -> UsageEventData | None:
    """Extract tracking dimensions from a JSON-RPC request payload."""

    try:
        message = json.loads(payload)
    except (UnicodeDecodeError, ValueError):
        return None
    if not isinstance(message, dict) or "id" not in message:
        return None
    method = message.get("method")
    if not isinstance(method, str) or not method:
        return None
    params = message.get("params")
    if not isinstance(params, dict):
        params = {}
    return UsageEventData(
        method=method[:METHOD_MAX_LENGTH],
        item=_extract_item(method, params),
        client_app=_extract_client_app(params),
    )


def _extract_item(method: str, params: dict[str, Any]) -> str | None:
    key = (
        "name"
        if method in {"tools/call", "prompts/get"}
        else "uri"
        if method == "resources/read"
        else None
    )
    if key is None:
        return None
    value = params.get(key)
    return value[:ITEM_MAX_LENGTH] if isinstance(value, str) and value else None


def _extract_client_app(params: dict[str, Any]) -> str | None:
    meta = params.get("_meta")
    if not isinstance(meta, dict):
        return None
    client_info = meta.get(CLIENT_INFO_META_KEY)
    if not isinstance(client_info, dict):
        return None
    name = client_info.get("name")
    return name[:CLIENT_APP_MAX_LENGTH] if isinstance(name, str) and name else None


def should_record(status: int) -> bool:
    """Return whether a gateway response represents authenticated traffic.

    Unauthenticated attempts are answered with HTTP 401 by the gateway's auth
    layer. Every other outcome — success, upstream failures, or a valid token
    rejected for missing scope (403) — belongs to an authenticated request.
    """

    return status != 401


class UsageRecorder:
    """Bounded, lifecycle-owned writer for usage events."""

    def __init__(
        self,
        session_factory: async_sessionmaker,
        *,
        queue_size: int = USAGE_QUEUE_SIZE,
        batch_size: int = USAGE_BATCH_SIZE,
    ) -> None:
        self._session_factory = session_factory
        self._queue: asyncio.Queue[UsageRecord | None] = asyncio.Queue(queue_size)
        self._batch_size = batch_size
        self._worker: asyncio.Task[None] | None = None
        self.dropped_events = 0

    async def start(self) -> None:
        if self._worker is None:
            self._worker = asyncio.create_task(self._run())

    def record(self, record: UsageRecord) -> None:
        try:
            self._queue.put_nowait(record)
        except asyncio.QueueFull:
            self.dropped_events += 1
            logger.warning(
                "Usage queue is full; dropping event for '%s'", record.server_name
            )

    async def stop(self) -> None:
        if self._worker is None:
            return
        await self._queue.join()
        await self._queue.put(None)
        await self._worker
        self._worker = None

    async def _run(self) -> None:
        while True:
            first = await self._queue.get()
            if first is None:
                self._queue.task_done()
                return
            batch = [first]
            while len(batch) < self._batch_size:
                try:
                    item = self._queue.get_nowait()
                except asyncio.QueueEmpty:
                    break
                if item is None:
                    self._queue.task_done()
                    break
                batch.append(item)
            try:
                await self._persist(batch)
            finally:
                for _ in batch:
                    self._queue.task_done()

    async def _persist(self, records: list[UsageRecord]) -> None:
        try:
            async with self._session_factory() as session:
                session.add_all(
                    [
                        UsageEvent(
                            server_name=record.server_name,
                            method=record.method,
                            item=record.item,
                            client_app=record.client_app,
                            status_code=record.status_code,
                            ts=record.ts,
                        )
                        for record in records
                    ]
                )
                await session.commit()
        except Exception:
            logger.exception("Failed to persist %d usage events", len(records))


class UsageTrackingMiddleware:
    """Buffering ASGI middleware that records authenticated JSON-RPC requests.

    Reads the request body once, extracts tracking dimensions, replays the body
    to the downstream FastMCP app, and persists the event in the background so
    tracing never adds latency to the proxied request. Events are recorded only
    when the gateway authenticates the request: unauthenticated attempts are
    answered with HTTP 401 and are skipped.
    """

    def __init__(
        self,
        app: ASGIApp,
        server_name: str,
        recorder: UsageRecorder,
        *,
        max_body_bytes: int = MAX_REQUEST_BODY_BYTES,
    ) -> None:
        self._app = app
        self._server_name = server_name
        self._recorder = recorder
        self._max_body_bytes = max_body_bytes

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            return await self._app(scope, receive, send)

        body = bytearray()
        while True:
            message = await receive()
            if message["type"] == "http.disconnect":
                return
            if message["type"] != "http.request":
                continue
            body.extend(message.get("body", b""))
            if len(body) > self._max_body_bytes:
                await _send_too_large(send)
                return
            if not message.get("more_body", False):
                break

        payload = bytes(body)
        event = extract_usage_event(payload)

        async def send_with_tracking(message: Message) -> None:
            if message["type"] == "http.response.start" and event is not None:
                status = message.get("status", 200)
                if should_record(status):
                    self._recorder.record(
                        UsageRecord(
                            server_name=self._server_name,
                            method=event.method,
                            item=event.item,
                            client_app=event.client_app,
                            status_code=status,
                            ts=datetime.now(UTC),
                        )
                    )
            await send(message)

        replayed = False

        async def replay_receive() -> Message:
            nonlocal replayed
            if not replayed:
                replayed = True
                return {
                    "type": "http.request",
                    "body": payload,
                    "more_body": False,
                }
            return await receive()

        return await self._app(scope, replay_receive, send_with_tracking)


async def _send_too_large(send: Send) -> None:
    body = b"Request body exceeds the 1 MiB gateway limit."
    await send(
        {
            "type": "http.response.start",
            "status": 413,
            "headers": [
                (b"content-type", b"text/plain; charset=utf-8"),
                (b"content-length", str(len(body)).encode()),
            ],
        }
    )
    await send({"type": "http.response.body", "body": body})


def apply_usage_tracing(
    app: ASGIApp,
    *,
    server_name: str,
    recorder: UsageRecorder | None,
) -> ASGIApp:
    """Wrap an MCP app with usage tracing when a database is configured."""

    if recorder is None:
        return app
    return UsageTrackingMiddleware(app, server_name, recorder)
