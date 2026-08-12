from __future__ import annotations

from collections.abc import Callable
from typing import TypedDict

import httpx2
import pytest
from fastapi.testclient import TestClient
from fastmcp.client.transports import StreamableHttpTransport
from pydantic import AnyHttpUrl, TypeAdapter

import proxy.servers.app as servers_app_module
from proxy.app.main import MCP_PROTOCOL_VERSION, create_app
from proxy.providers import ServerAuthProviderConfig
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


def server_config(upstream_url: str = "http://127.0.0.1:9/mcp") -> McpServerConfig:
    return McpServerConfig.model_validate(
        {
            "name": "calendar",
            "upstream_url": upstream_url,
            "auth": {
                "provider": "keycloak",
                "realm_url": "https://identity.example/realms/test",
                "required_scopes": ["mcp"],
            },
        }
    )


@pytest.fixture(autouse=True)
def use_static_auth_provider(monkeypatch: pytest.MonkeyPatch) -> None:
    def load_static_provider(
        _config: ServerAuthProviderConfig,
        *,
        base_url: str,
    ) -> StaticAuthProvider:
        return StaticAuthProvider(base_url=base_url, required_scopes=["mcp"])

    monkeypatch.setattr(servers_app_module, "load_auth_provider", load_static_provider)


@pytest.fixture()
def boot_gateway(
    postgres_url: str,
) -> Callable[[list[McpServerConfig] | None, dict[str, object]], TestClient]:
    def build(
        servers: list[McpServerConfig] | None = None,
        **extra: object,
    ) -> TestClient:
        servers = servers or [server_config()]
        seed_servers(postgres_url, servers)
        config = GatewayConfig.model_validate(
            {"database": {"url": postgres_url}, **extra}
        )
        return TestClient(create_app(config))

    return build


def modern_headers(method: str) -> dict[str, str]:
    return {
        "Accept": "application/json, text/event-stream",
        "MCP-Protocol-Version": MCP_PROTOCOL_VERSION,
        "MCP-Method": method,
    }


def test_gateway_mounts_named_server_and_fastmcp_enforces_auth(
    boot_gateway: Callable[..., TestClient],
) -> None:
    with boot_gateway() as client:
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


def test_authenticated_modern_response_has_no_legacy_session_header(
    boot_gateway: Callable[..., TestClient],
) -> None:
    headers = modern_headers("server/discover") | {
        "Authorization": "Bearer valid-token"
    }

    with boot_gateway() as client:
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
    boot_gateway: Callable[..., TestClient],
) -> None:
    upstream_requests: list[dict[str, str]] = []
    upstream = FakeModernUpstream(upstream_requests)

    def in_process_transport(
        upstream_url: str,
        *,
        verify_tls: bool = True,
        forward_client_credentials: bool = False,
    ) -> StreamableHttpTransport:
        return create_upstream_transport(
            upstream_url,
            verify_tls=verify_tls,
            forward_client_credentials=forward_client_credentials,
            http_transport=httpx2.MockTransport(upstream.handle_request),
        )

    monkeypatch.setattr(
        servers_app_module, "create_upstream_transport", in_process_transport
    )
    headers = modern_headers("tools/list") | {
        "Authorization": "Bearer valid-token",
        "Cookie": "front-session=secret",
        "Proxy-Authorization": "Basic c2VjcmV0",
    }

    with boot_gateway() as client:
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


def test_well_known_mcp_servers_publishes_public_endpoints(
    boot_gateway: Callable[..., TestClient],
) -> None:
    with boot_gateway(public_base_url="https://gateway.example") as client:
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


def test_well_known_document_serves_cors_headers_for_configured_origins(
    boot_gateway: Callable[..., TestClient],
) -> None:
    with boot_gateway(cors_origins=[AnyHttpUrl("http://localhost:3000")]) as client:
        response = client.get(
            "/.well-known/mcp-servers",
            headers={"Origin": "http://localhost:3000"},
        )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:3000"


def test_well_known_document_is_public_without_auth(
    boot_gateway: Callable[..., TestClient],
) -> None:
    with boot_gateway() as client:
        response = client.get("/.well-known/mcp-servers")

    assert response.status_code == 200


def none_server() -> McpServerConfig:
    return McpServerConfig.model_validate(
        {
            "name": "relay",
            "upstream_url": "http://127.0.0.1:9/mcp",
            "auth": {"provider": "none"},
            "forward_client_credentials": True,
        }
    )


def use_real_auth_provider(monkeypatch: pytest.MonkeyPatch) -> None:
    from proxy import providers as providers_module

    monkeypatch.setattr(
        servers_app_module, "load_auth_provider", providers_module.load_auth_provider
    )


def use_mock_upstream(
    monkeypatch: pytest.MonkeyPatch,
    upstream: FakeModernUpstream,
) -> None:
    def in_process_transport(
        upstream_url: str,
        *,
        verify_tls: bool = True,
        forward_client_credentials: bool = False,
    ) -> StreamableHttpTransport:
        return create_upstream_transport(
            upstream_url,
            verify_tls=verify_tls,
            forward_client_credentials=forward_client_credentials,
            http_transport=httpx2.MockTransport(upstream.handle_request),
        )

    monkeypatch.setattr(
        servers_app_module, "create_upstream_transport", in_process_transport
    )


def test_none_provider_relays_client_authorization_to_upstream(
    monkeypatch: pytest.MonkeyPatch,
    boot_gateway: Callable[..., TestClient],
) -> None:
    upstream_requests: list[dict[str, str]] = []
    upstream = FakeModernUpstream(upstream_requests)
    use_real_auth_provider(monkeypatch)
    use_mock_upstream(monkeypatch, upstream)
    with_token = modern_headers("tools/list") | {
        "Authorization": "Bearer upstream-token"
    }

    with boot_gateway([none_server()]) as client:
        with_authorization = client.post(
            "/relay/mcp", headers=with_token, json=modern_request("tools/list")
        )
        without_authorization = client.post(
            "/relay/mcp",
            headers=modern_headers("tools/list"),
            json=modern_request("tools/list"),
        )

    assert with_authorization.status_code == 200
    assert without_authorization.status_code == 200
    assert len(upstream_requests) == 2
    assert upstream_requests[0].get("authorization") == "Bearer upstream-token"
    assert "authorization" not in upstream_requests[1]
    assert all("cookie" not in request for request in upstream_requests)
    assert all("proxy-authorization" not in request for request in upstream_requests)


def test_none_provider_skips_oauth_and_serves_discovery_unauthenticated(
    monkeypatch: pytest.MonkeyPatch,
    boot_gateway: Callable[..., TestClient],
) -> None:
    use_real_auth_provider(monkeypatch)

    with boot_gateway([none_server()]) as client:
        discovery = client.post(
            "/relay/mcp",
            headers=modern_headers("server/discover"),
            json=modern_request("server/discover"),
        )
        protected_resource = client.get(
            "/.well-known/oauth-protected-resource/relay/mcp"
        )

    assert discovery.status_code == 200
    assert discovery.json()["result"]["supportedVersions"] == [MCP_PROTOCOL_VERSION]
    assert "www-authenticate" not in discovery.headers
    assert protected_resource.status_code == 404


def test_none_provider_publishes_none_in_discovery_document(
    monkeypatch: pytest.MonkeyPatch,
    boot_gateway: Callable[..., TestClient],
) -> None:
    use_real_auth_provider(monkeypatch)

    with boot_gateway(
        [none_server()], public_base_url="https://gateway.example"
    ) as client:
        response = client.get("/.well-known/mcp-servers")

    assert response.status_code == 200
    assert response.json() == {
        "servers": [
            {
                "name": "relay",
                "description": "",
                "url": "https://gateway.example/relay/mcp",
                "auth": "none",
            }
        ]
    }
