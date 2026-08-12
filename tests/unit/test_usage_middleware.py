from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Self

import pytest

from proxy.app.usage.middleware import (
    UsageEventData,
    UsageRecord,
    UsageRecorder,
    UsageTrackingMiddleware,
    extract_usage_event,
    should_record,
)


def modern_payload(method: str, **params: object) -> bytes:
    request = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": method,
        "params": {
            **params,
            "_meta": {
                "io.modelcontextprotocol/protocolVersion": "2026-07-28",
                "io.modelcontextprotocol/clientCapabilities": {},
                "io.modelcontextprotocol/clientInfo": {
                    "name": "gateway-test",
                    "version": "1",
                },
            },
        },
    }
    return json.dumps(request).encode()


def test_extract_usage_event_tracks_tool_call_name() -> None:
    event = extract_usage_event(modern_payload("tools/call", name="get_weather"))

    assert event == UsageEventData(
        method="tools/call",
        item="get_weather",
        client_app="gateway-test",
    )


def test_extract_usage_event_tracks_resource_uri() -> None:
    event = extract_usage_event(modern_payload("resources/read", uri="file:///notes"))

    assert event is not None
    assert event.item == "file:///notes"


def test_extract_usage_event_tracks_prompt_name() -> None:
    event = extract_usage_event(modern_payload("prompts/get", name="summarize"))

    assert event is not None
    assert event.item == "summarize"


def test_extract_usage_event_leaves_unkeyed_method_itemless() -> None:
    event = extract_usage_event(modern_payload("ping"))

    assert event is not None
    assert event.method == "ping"
    assert event.item is None
    assert event.client_app == "gateway-test"


def test_extract_usage_event_ignores_missing_client_info() -> None:
    payload = json.dumps(
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {"name": "get_weather", "_meta": {}},
        }
    ).encode()

    event = extract_usage_event(payload)

    assert event is not None
    assert event.client_app is None


def test_extract_usage_event_ignores_notifications() -> None:
    payload = json.dumps(
        {"jsonrpc": "2.0", "method": "notifications/cancelled", "params": {}}
    ).encode()

    assert extract_usage_event(payload) is None


def test_extract_usage_event_ignores_invalid_json() -> None:
    assert extract_usage_event(b"not json") is None
    assert extract_usage_event(b"") is None


def test_extract_usage_event_ignores_batches() -> None:
    payload = json.dumps([json.loads(modern_payload("ping"))]).encode()

    assert extract_usage_event(payload) is None


def test_extract_usage_event_ignores_missing_method() -> None:
    payload = json.dumps({"jsonrpc": "2.0", "id": 1, "params": {}}).encode()

    assert extract_usage_event(payload) is None


def test_extract_usage_event_bounds_database_dimensions() -> None:
    payload = json.loads(modern_payload("tools/call", name="i" * 300))
    payload["params"]["_meta"]["io.modelcontextprotocol/clientInfo"]["name"] = "c" * 200
    event = extract_usage_event(json.dumps(payload).encode())

    assert event is not None
    assert len(event.item or "") == 255
    assert len(event.client_app or "") == 128


async def test_middleware_rejects_oversized_body_before_downstream() -> None:
    called = False
    sent: list[dict] = []

    async def app(scope: dict, receive: object, send: object) -> None:
        nonlocal called
        called = True

    class Recorder:
        def record(self, record: object) -> None:
            raise AssertionError("oversized requests must not be recorded")

    messages = iter([{"type": "http.request", "body": b"12345", "more_body": False}])

    async def receive() -> dict:
        return next(messages)

    async def send(message: dict) -> None:
        sent.append(message)

    middleware = UsageTrackingMiddleware(
        app,
        "calendar",
        Recorder(),  # type: ignore[arg-type]
        max_body_bytes=4,
    )
    await middleware({"type": "http"}, receive, send)

    assert not called
    assert sent[0]["status"] == 413


async def test_middleware_stops_on_client_disconnect() -> None:
    called = False

    async def app(scope: dict, receive: object, send: object) -> None:
        nonlocal called
        called = True

    async def receive() -> dict:
        return {"type": "http.disconnect"}

    async def send(message: dict) -> None:
        raise AssertionError(f"disconnected requests cannot send {message}")

    middleware = UsageTrackingMiddleware(
        app,
        "calendar",
        object(),  # type: ignore[arg-type]
    )
    await middleware({"type": "http"}, receive, send)

    assert not called


async def test_usage_recorder_batches_and_drains_on_stop() -> None:
    persisted: list[object] = []
    commits = 0

    class Session:
        async def __aenter__(self) -> Self:
            return self

        async def __aexit__(self, *args: object) -> None:
            return None

        def add_all(self, records: list[object]) -> None:
            persisted.extend(records)

        async def commit(self) -> None:
            nonlocal commits
            commits += 1

    recorder = UsageRecorder(lambda: Session(), batch_size=10)  # type: ignore[arg-type]
    await recorder.start()
    for method in ("tools/list", "tools/call", "resources/list"):
        recorder.record(
            UsageRecord(
                server_name="calendar",
                method=method,
                item=None,
                client_app="test",
                status_code=200,
                ts=datetime.now(UTC),
            )
        )

    await recorder.stop()

    assert len(persisted) == 3
    assert commits == 1


def test_usage_recorder_counts_queue_overflow() -> None:
    recorder = UsageRecorder(object(), queue_size=1)  # type: ignore[arg-type]
    record = UsageRecord(
        server_name="calendar",
        method="tools/list",
        item=None,
        client_app="test",
        status_code=200,
        ts=datetime.now(UTC),
    )

    recorder.record(record)
    recorder.record(record)

    assert recorder.dropped_events == 1


@pytest.mark.parametrize("status", [200, 201, 400, 403, 404, 500, 503])
def test_should_record_authenticated_outcomes(status: int) -> None:
    assert should_record(status)


def test_should_record_skips_unauthenticated_status() -> None:
    assert not should_record(401)
