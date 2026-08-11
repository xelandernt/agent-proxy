from __future__ import annotations

import asyncio
import json
import time
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from typing import TypedDict

import httpx2
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

import proxy.servers.app as servers_app_module
from proxy.app.main import MCP_PROTOCOL_VERSION, create_app
from proxy.database import create_engine
from proxy.servers.models import McpServerConfig
from proxy.settings import GatewayConfig
from proxy.transport import create_upstream_transport
from tests.integration.helpers import seed_servers
from tests.support import StaticAuthProvider


class ClientInfo(TypedDict):
    name: str
    version: str


class ClientCapabilities(TypedDict):
    pass


ClientMetadata = TypedDict(
    "ClientMetadata",
    {
        "io.modelcontextprotocol/protocolVersion": str,
        "io.modelcontextprotocol/clientCapabilities": ClientCapabilities,
        "io.modelcontextprotocol/clientInfo": ClientInfo,
    },
)


def usage_request(method: str, **params: object) -> dict[str, object]:
    return {
        "jsonrpc": "2.0",
        "id": 1,
        "method": method,
        "params": {
            **params,
            "_meta": {
                "io.modelcontextprotocol/protocolVersion": MCP_PROTOCOL_VERSION,
                "io.modelcontextprotocol/clientCapabilities": {},
                "io.modelcontextprotocol/clientInfo": {
                    "name": "gateway-test",
                    "version": "1",
                },
            },
        },
    }


def usage_headers(method: str, **extra: str) -> dict[str, str]:
    return {
        "Accept": "application/json, text/event-stream",
        "MCP-Protocol-Version": MCP_PROTOCOL_VERSION,
        "MCP-Method": method,
        "Authorization": "Bearer valid-token",
        **extra,
    }


class FakeUpstream:
    """In-process upstream answering the discover handshake and method calls."""

    async def handle_request(self, request: httpx2.Request) -> httpx2.Response:
        body = json.loads(request.content)
        method = body["method"]
        result: dict[str, object]
        if method == "server/discover":
            result = {
                "cacheScope": "private",
                "resultType": "complete",
                "supportedVersions": [MCP_PROTOCOL_VERSION],
                "capabilities": {"tools": {"listChanged": False}},
            }
        elif method == "tools/list":
            result = {"cacheScope": "private", "resultType": "complete", "tools": []}
        elif method == "tools/call":
            result = {
                "cacheScope": "private",
                "resultType": "complete",
                "content": [{"type": "text", "text": "ok"}],
                "isError": False,
            }
        elif method == "resources/list":
            result = {
                "cacheScope": "private",
                "resultType": "complete",
                "resources": [],
            }
        else:
            result = {"cacheScope": "private", "resultType": "complete"}
        result["ttlMs"] = 0
        result["_meta"] = {
            "io.modelcontextprotocol/serverInfo": {
                "name": "fake-upstream",
                "version": "1",
            }
        }
        return httpx2.Response(
            status_code=200,
            json={"jsonrpc": "2.0", "id": body["id"], "result": result},
        )


@pytest.fixture(autouse=True)
def use_static_auth_provider(monkeypatch: pytest.MonkeyPatch) -> None:
    def load_static_provider(
        _config: object,
        *,
        base_url: str,
    ) -> StaticAuthProvider:
        return StaticAuthProvider(base_url=base_url, required_scopes=["mcp"])

    monkeypatch.setattr(servers_app_module, "load_auth_provider", load_static_provider)


@pytest.fixture()
def usage_client(
    postgres_url: str,
    monkeypatch: pytest.MonkeyPatch,
) -> Iterator[TestClient]:
    def in_process_transport(
        upstream_url: str,
        *,
        verify_tls: bool = True,
    ) -> object:
        return create_upstream_transport(
            upstream_url,
            verify_tls=verify_tls,
            http_transport=httpx2.MockTransport(FakeUpstream().handle_request),
        )

    monkeypatch.setattr(
        servers_app_module, "create_upstream_transport", in_process_transport
    )
    server = McpServerConfig.model_validate(
        {
            "name": "calendar",
            "upstream_url": "http://127.0.0.1:9/mcp",
            "auth": {
                "provider": "keycloak",
                "realm_url": "https://identity.example/realms/test",
            },
        }
    )
    quiet = McpServerConfig.model_validate(
        {
            "name": "notes",
            "upstream_url": "http://127.0.0.1:9/mcp",
            "auth": {
                "provider": "keycloak",
                "realm_url": "https://identity.example/realms/test",
            },
        }
    )
    seed_servers(postgres_url, [server, quiet])
    config = GatewayConfig.model_validate(
        {
            "public_base_url": "https://gateway.example",
            "database": {"url": postgres_url},
        }
    )
    app = create_app(config)
    with TestClient(app) as client:
        asyncio.run(_truncate_usage_events(postgres_url))
        yield client


async def _truncate_usage_events(postgres_url: str) -> None:
    engine = create_engine(postgres_url)
    try:
        async with engine.begin() as connection:
            await connection.execute(text("TRUNCATE usage_events"))
    finally:
        await engine.dispose()


def _report_window() -> dict[str, str]:
    end = datetime.now(UTC) + timedelta(minutes=1)
    start = end - timedelta(hours=1)
    return {
        "from": start.isoformat(),
        "to": end.isoformat(),
    }


def _fetch_report(
    client: TestClient,
    expected_total: int | None = None,
) -> dict[str, object]:
    deadline = time.monotonic() + 5.0
    last: dict[str, object] = {}
    while time.monotonic() < deadline:
        response = client.get("/api/servers/calendar/usage", params=_report_window())
        assert response.status_code == 200
        last = response.json()
        if expected_total is None or last["total"] >= expected_total:
            return last
        time.sleep(0.05)
    return last


def test_usage_tracks_and_queries_requests(usage_client: TestClient) -> None:
    client = usage_client
    for _ in range(2):
        response = client.post(
            "/calendar/mcp",
            headers=usage_headers("tools/list"),
            json=usage_request("tools/list"),
        )
        assert response.status_code == 200
    response = client.post(
        "/calendar/mcp",
        headers=usage_headers("tools/call", **{"MCP-Name": "get_weather"}),
        json=usage_request("tools/call", name="get_weather"),
    )
    assert response.status_code == 200

    report = _fetch_report(client, expected_total=3)

    assert report["server"] == "calendar"
    assert report["total"] == 3
    assert report["tools"] == [{"name": "get_weather", "count": 1}]
    assert {"name": "tools/list", "count": 2} in report["methods"]
    assert {"name": "tools/call", "count": 1} in report["methods"]
    assert report["clients"] == [{"name": "gateway-test", "count": 3}]
    assert report["statuses"] == [{"name": "200", "count": 3}]


def test_usage_tracks_response_status(usage_client: TestClient) -> None:
    client = usage_client
    response = client.post(
        "/calendar/mcp",
        headers=usage_headers("tools/list"),
        json=usage_request("tools/list"),
    )
    assert response.status_code == 200
    rejected = client.post(
        "/calendar/mcp",
        headers=usage_headers("tools/call"),
        json=usage_request("tools/call", name="get_weather"),
    )
    assert rejected.status_code == 400

    report = _fetch_report(client, expected_total=2)

    assert report["statuses"] == [
        {"name": "200", "count": 1},
        {"name": "400", "count": 1},
    ]


def test_usage_window_filters_events(usage_client: TestClient) -> None:
    client = usage_client
    response = client.post(
        "/calendar/mcp",
        headers=usage_headers("resources/list"),
        json=usage_request("resources/list"),
    )
    assert response.status_code == 200
    _fetch_report(client, expected_total=1)

    end = datetime.now(UTC) + timedelta(minutes=1)
    past = (end - timedelta(hours=2)).isoformat()
    response = client.get(
        "/api/servers/calendar/usage",
        params={"from": past, "to": (end - timedelta(hours=1, minutes=-1)).isoformat()},
    )

    assert response.status_code == 200
    assert response.json()["total"] == 0


def test_usage_skips_unauthenticated_requests(usage_client: TestClient) -> None:
    client = usage_client
    no_auth_headers = {
        name: value
        for name, value in usage_headers("tools/list").items()
        if name != "Authorization"
    }
    for headers in (
        no_auth_headers,
        usage_headers("tools/list") | {"Authorization": "Bearer invalid-token"},
    ):
        response = client.post(
            "/calendar/mcp",
            headers=headers,
            json=usage_request("tools/list"),
        )
        assert response.status_code == 401

    response = client.post(
        "/calendar/mcp",
        headers=usage_headers("tools/list"),
        json=usage_request("tools/list"),
    )
    assert response.status_code == 200

    report = _fetch_report(client, expected_total=1)

    assert report["total"] == 1
    assert report["methods"] == [{"name": "tools/list", "count": 1}]


def test_usage_unknown_server_returns_404(usage_client: TestClient) -> None:
    response = usage_client.get("/api/servers/unknown/usage", params=_report_window())

    assert response.status_code == 404


def test_usage_rejects_inverted_window(usage_client: TestClient) -> None:
    end = datetime.now(UTC).isoformat()
    start = (datetime.now(UTC) + timedelta(hours=1)).isoformat()
    response = usage_client.get(
        "/api/servers/calendar/usage",
        params={"from": start, "to": end},
    )

    assert response.status_code == 422


def _aligned_window(hours: int) -> dict[str, str]:
    end = datetime.now(UTC).replace(second=0, microsecond=0) + timedelta(minutes=1)
    start = end - timedelta(hours=hours)
    return {
        "from": start.isoformat(),
        "to": end.isoformat(),
    }


def _fetch_series(
    client: TestClient,
    params: dict[str, str],
    expected_total: int,
) -> dict[str, object]:
    deadline = time.monotonic() + 5.0
    last: dict[str, object] = {}
    while time.monotonic() < deadline:
        response = client.get(
            "/api/servers/calendar/usage/series",
            params=params,
        )
        assert response.status_code == 200
        last = response.json()
        points = last["points"]
        if sum(point["total"] for point in points) >= expected_total:
            return last
        time.sleep(0.05)
    return last


def test_usage_series_buckets_requests(usage_client: TestClient) -> None:
    client = usage_client
    for _ in range(2):
        response = client.post(
            "/calendar/mcp",
            headers=usage_headers("tools/list"),
            json=usage_request("tools/list"),
        )
        assert response.status_code == 200
    response = client.post(
        "/calendar/mcp",
        headers=usage_headers("tools/call", **{"MCP-Name": "get_weather"}),
        json=usage_request("tools/call", name="get_weather"),
    )
    assert response.status_code == 200

    params = _aligned_window(1) | {"bucket": "minute"}
    series = _fetch_series(client, params, expected_total=3)

    points = series["points"]
    assert isinstance(points, list)
    assert len(points) == 60
    assert sum(point["total"] for point in points) == 3
    active = [point for point in points if point["total"] > 0]
    assert len(active) >= 1
    for point in active:
        assert point["methods"] == [
            {"name": "tools/list", "count": 2},
            {"name": "tools/call", "count": 1},
        ]
        assert point["tools"] == [{"name": "get_weather", "count": 1}]
        assert point["clients"] == [{"name": "gateway-test", "count": 3}]
        assert point["statuses"] == [{"name": "200", "count": 3}]


def test_usage_series_picks_bucket_for_window(usage_client: TestClient) -> None:
    response = usage_client.get(
        "/api/servers/calendar/usage/series",
        params=_aligned_window(1),
    )

    assert response.status_code == 200
    assert response.json()["bucket"] == "minute"

    response = usage_client.get(
        "/api/servers/calendar/usage/series",
        params=_aligned_window(8),
    )

    assert response.status_code == 200
    assert response.json()["bucket"] == "hour"

    response = usage_client.get(
        "/api/servers/calendar/usage/series",
        params=_aligned_window(24 * 8),
    )

    assert response.status_code == 200
    assert response.json()["bucket"] == "day"


def test_usage_series_rejects_invalid_bucket(usage_client: TestClient) -> None:
    response = usage_client.get(
        "/api/servers/calendar/usage/series",
        params=_aligned_window(1) | {"bucket": "month"},
    )

    assert response.status_code == 422


def test_usage_series_unknown_server_returns_404(usage_client: TestClient) -> None:
    response = usage_client.get(
        "/api/servers/unknown/usage/series",
        params=_aligned_window(1),
    )

    assert response.status_code == 404


def test_usage_series_rejects_inverted_window(usage_client: TestClient) -> None:
    end = datetime.now(UTC).isoformat()
    start = (datetime.now(UTC) + timedelta(hours=1)).isoformat()
    response = usage_client.get(
        "/api/servers/calendar/usage/series",
        params={"from": start, "to": end},
    )

    assert response.status_code == 422


def test_servers_usage_series_fills_empty_servers(usage_client: TestClient) -> None:
    client = usage_client
    for _ in range(2):
        response = client.post(
            "/calendar/mcp",
            headers=usage_headers("tools/list"),
            json=usage_request("tools/list"),
        )
        assert response.status_code == 200

    params = _aligned_window(24)
    deadline = time.monotonic() + 5.0
    last: dict[str, object] = {}
    while time.monotonic() < deadline:
        response = client.get("/api/servers/series", params=params)
        assert response.status_code == 200
        last = response.json()
        servers = {entry["name"]: entry for entry in last["servers"]}
        if sum(point["total"] for point in servers["calendar"]["points"]) >= 2:
            break
        time.sleep(0.05)

    assert response.status_code == 200
    servers = {entry["name"]: entry for entry in last["servers"]}
    assert set(servers) == {"calendar", "notes"}
    calendar = servers["calendar"]["points"]
    assert len(calendar) == 25
    assert sum(point["total"] for point in calendar) == 2
    notes = servers["notes"]["points"]
    assert len(notes) == 25
    assert all(point["total"] == 0 for point in notes)
