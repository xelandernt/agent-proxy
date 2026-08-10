from __future__ import annotations

from typing import TypedDict

import httpx2
import pytest
from fastapi.testclient import TestClient
from pydantic import AnyHttpUrl, TypeAdapter

from fastmcp.client.transports import StreamableHttpTransport
import proxy.app.main as main_module
from proxy.app.main import MCP_PROTOCOL_VERSION, create_app
from proxy.providers import AuthProviderConfig
from proxy.settings import GatewayConfig
from proxy.transport import create_upstream_transport
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


class ModernRequestParams(TypedDict):
    _meta: ClientMetadata


class ModernRequest(TypedDict):
    jsonrpc: str
    id: int
    method: str
    params: ModernRequestParams


class FakeModernUpstream:
    def __init__(self, requests: list[dict[str, str]]) -> None:
        self.requests = requests

    async def handle_request(self, request: httpx2.Request) -> httpx2.Response:
        body = TypeAdapter(ModernRequest).validate_json(request.content)
        self.requests.append(dict(request.headers))
        return httpx2.Response(
            status_code=200,
            json={
                "jsonrpc": "2.0",
                "id": body["id"],
                "result": {
                    "cacheScope": "private",
                    "resultType": "complete",
                    "tools": [],
                    "ttlMs": 0,
                    "_meta": {
                        "io.modelcontextprotocol/serverInfo": {
                            "name": "fake-upstream",
                            "version": "1",
                        }
                    },
                },
            },
        )


def modern_request(method: str) -> ModernRequest:
    return {
        "jsonrpc": "2.0",
        "id": 1,
        "method": method,
        "params": {
            "_meta": {
                "io.modelcontextprotocol/protocolVersion": MCP_PROTOCOL_VERSION,
                "io.modelcontextprotocol/clientCapabilities": {},
                "io.modelcontextprotocol/clientInfo": {
                    "name": "gateway-test",
                    "version": "1",
                },
            }
        },
    }


def gateway_config(upstream_url: str = "http://127.0.0.1:9/mcp") -> GatewayConfig:
    return GatewayConfig.model_validate(
        {
            "public_base_url": "https://gateway.example",
            "servers": [
                {
                    "name": "calendar",
                    "upstream_url": upstream_url,
                    "auth": {
                        "provider": "keycloak",
                        "realm_url": "https://identity.example/realms/test",
                        "required_scopes": ["mcp"],
                    },
                }
            ],
        }
    )


@pytest.fixture(autouse=True)
def use_static_auth_provider(monkeypatch: pytest.MonkeyPatch) -> None:
    def load_static_provider(
        _config: AuthProviderConfig,
        *,
        base_url: str,
    ) -> StaticAuthProvider:
        return StaticAuthProvider(base_url=base_url, required_scopes=["mcp"])

    monkeypatch.setattr(main_module, "load_auth_provider", load_static_provider)


def modern_headers(method: str) -> dict[str, str]:
    return {
        "Accept": "application/json, text/event-stream",
        "MCP-Protocol-Version": MCP_PROTOCOL_VERSION,
        "MCP-Method": method,
    }


def test_gateway_mounts_named_server_and_fastmcp_enforces_auth() -> None:
    app = create_app(gateway_config())

    with TestClient(app) as client:
        response = client.post(
            "/calendar/mcp",
            headers=modern_headers("server/discover"),
            json=modern_request("server/discover"),
        )
        unknown = client.post(
            "/unknown/mcp",
            headers=modern_headers("server/discover"),
            json=modern_request("server/discover"),
        )

    assert response.status_code == 401
    assert response.headers["www-authenticate"].startswith("Bearer")
    assert unknown.status_code == 404


def test_authenticated_modern_response_has_no_legacy_session_header() -> None:
    app = create_app(gateway_config())
    headers = modern_headers("server/discover") | {
        "Authorization": "Bearer valid-token"
    }

    with TestClient(app) as client:
        response = client.post(
            "/calendar/mcp",
            headers=headers,
            json=modern_request("server/discover"),
        )

    assert response.status_code == 200
    assert "mcp-session-id" not in response.headers
    assert response.json()["result"]["supportedVersions"] == [MCP_PROTOCOL_VERSION]


def test_front_credentials_never_reach_upstream(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    upstream_requests: list[dict[str, str]] = []
    upstream = FakeModernUpstream(upstream_requests)

    def in_process_transport(
        upstream_url: str,
        *,
        verify_tls: bool = True,
    ) -> StreamableHttpTransport:
        return create_upstream_transport(
            upstream_url,
            verify_tls=verify_tls,
            http_transport=httpx2.MockTransport(upstream.handle_request),
        )

    monkeypatch.setattr(main_module, "create_upstream_transport", in_process_transport)
    app = create_app(gateway_config())
    headers = modern_headers("tools/list") | {
        "Authorization": "Bearer valid-token",
        "Cookie": "front-session=secret",
        "Proxy-Authorization": "Basic c2VjcmV0",
    }

    with TestClient(app) as client:
        response = client.post(
            "/calendar/mcp",
            headers=headers,
            json=modern_request("tools/list"),
        )

    assert response.status_code == 200
    assert upstream_requests
    assert all("authorization" not in request for request in upstream_requests)
    assert all("cookie" not in request for request in upstream_requests)
    assert all("proxy-authorization" not in request for request in upstream_requests)
    assert upstream_requests[-1]["mcp-protocol-version"] == MCP_PROTOCOL_VERSION
    assert upstream_requests[-1]["mcp-method"] == "tools/list"


def test_well_known_mcp_servers_publishes_public_endpoints() -> None:
    app = create_app(gateway_config())

    with TestClient(app) as client:
        response = client.get("/.well-known/mcp-servers")

    assert response.status_code == 200
    assert response.json() == {
        "servers": [
            {
                "name": "calendar",
                "description": "",
                "url": "https://gateway.example/calendar/mcp",
                "auth": "oauth2",
            }
        ]
    }


def test_well_known_document_serves_cors_headers_for_configured_origins() -> None:
    config = gateway_config()
    config.cors_origins = [AnyHttpUrl("http://localhost:3000")]
    app = create_app(config)

    with TestClient(app) as client:
        response = client.get(
            "/.well-known/mcp-servers",
            headers={"Origin": "http://localhost:3000"},
        )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:3000"


def test_well_known_document_is_public_without_auth() -> None:
    app = create_app(gateway_config())

    with TestClient(app) as client:
        response = client.get("/.well-known/mcp-servers")

    assert response.status_code == 200
