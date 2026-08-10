from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import Awaitable, Callable, MutableMapping
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from mcp.types import CLIENT_INFO_META_KEY
from sqlalchemy.ext.asyncio import AsyncEngine

from proxy.app.usage.models import UsageEvent
from proxy.database import create_session_factory

logger = logging.getLogger(__name__)

Scope = MutableMapping[str, Any]
Message = MutableMapping[str, Any]
Receive = Callable[[], Awaitable[Message]]
Send = Callable[[Message], Awaitable[None]]
ASGIApp = Callable[[Scope, Receive, Send], Awaitable[None]]


@dataclass(frozen=True, slots=True)
class UsageEventData:
    """One trackable JSON-RPC request, extracted from the wire payload."""

    method: str
    item: str | None
    client_app: str | None


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
        method=method,
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
    return value if isinstance(value, str) and value else None


def _extract_client_app(params: dict[str, Any]) -> str | None:
    meta = params.get("_meta")
    if not isinstance(meta, dict):
        return None
    client_info = meta.get(CLIENT_INFO_META_KEY)
    if not isinstance(client_info, dict):
        return None
    name = client_info.get("name")
    return name if isinstance(name, str) and name else None


def should_record(status: int) -> bool:
    """Return whether a gateway response represents authenticated traffic.

    Unauthenticated attempts are answered with HTTP 401 by the gateway's auth
    layer. Every other outcome — success, upstream failures, or a valid token
    rejected for missing scope (403) — belongs to an authenticated request.
    """

    return status != 401


class UsageTrackingMiddleware:
    """Buffering ASGI middleware that records authenticated JSON-RPC requests.

    Reads the request body once, extracts tracking dimensions, replays the body
    to the downstream FastMCP app, and persists the event in the background so
    tracing never adds latency to the proxied request. Events are recorded only
    when the gateway authenticates the request: unauthenticated attempts are
    answered with HTTP 401 and are skipped.
    """

    def __init__(self, app: ASGIApp, server_name: str, engine: AsyncEngine) -> None:
        self._app = app
        self._server_name = server_name
        self._session_factory = create_session_factory(engine)

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            return await self._app(scope, receive, send)

        body = b""
        while True:
            message = await receive()
            if message["type"] != "http.request":
                continue
            body += message.get("body", b"")
            if not message.get("more_body", False):
                break

        event = extract_usage_event(body)

        async def send_with_tracking(message: Message) -> None:
            if message["type"] == "http.response.start" and event is not None:
                status = message.get("status", 200)
                if should_record(status):
                    self._record(event, status)
            await send(message)

        replayed = False

        async def replay_receive() -> Message:
            nonlocal replayed
            if not replayed:
                replayed = True
                return {"type": "http.request", "body": body, "more_body": False}
            return await receive()

        return await self._app(scope, replay_receive, send_with_tracking)

    def _record(self, event: UsageEventData, status_code: int) -> None:
        session_factory = self._session_factory
        server_name = self._server_name
        ts = datetime.now(UTC)

        async def persist() -> None:
            try:
                async with session_factory() as session:
                    session.add(
                        UsageEvent(
                            server_name=server_name,
                            method=event.method,
                            item=event.item,
                            client_app=event.client_app,
                            status_code=status_code,
                            ts=ts,
                        )
                    )
                    await session.commit()
            except Exception:
                logger.exception(
                    "Failed to persist usage event for server '%s'", server_name
                )

        try:
            asyncio.create_task(persist())
        except Exception:
            logger.exception("Failed to schedule usage event persistence")


def apply_usage_tracing(
    app: ASGIApp,
    *,
    server_name: str,
    engine: AsyncEngine | None,
) -> ASGIApp:
    """Wrap an MCP app with usage tracing when a database is configured."""

    if engine is None:
        return app
    return UsageTrackingMiddleware(app, server_name, engine)
