from __future__ import annotations

import json

import pytest

from proxy.app.usage.middleware import (
    UsageEventData,
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


@pytest.mark.parametrize("status", [200, 201, 400, 403, 404, 500, 503])
def test_should_record_authenticated_outcomes(status: int) -> None:
    assert should_record(status)


def test_should_record_skips_unauthenticated_status() -> None:
    assert not should_record(401)
