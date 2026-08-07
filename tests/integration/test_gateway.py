from __future__ import annotations

from typing import TypedDict

import httpx2
import pytest
from fastapi import FastAPI
from fastapi.openapi.models import HTTPBearer, OpenAPI, Parameter, PathItem
from fastapi.testclient import TestClient
from pydantic import TypeAdapter

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


def test_gateway_publishes_swagger_scalar_and_typed_openapi() -> None:
    app = create_app(gateway_config())

    with TestClient(app) as client:
        openapi_response = client.get("/openapi.json")
        swagger_response = client.get("/docs")
        scalar_response = client.get("/scalar")
        redoc_response = client.get("/redoc")

    assert isinstance(app, FastAPI)
    assert openapi_response.status_code == 200
    document = OpenAPI.model_validate(openapi_response.json())
    assert document.info.title == "agent-proxy"
    assert document.servers is not None
    assert [server.url for server in document.servers] == ["https://gateway.example/"]

    assert document.paths is not None
    assert set(document.paths) == {"/calendar/mcp"}
    path_item = PathItem.model_validate(document.paths["/calendar/mcp"])
    assert path_item.post is not None
    assert path_item.post.operationId == "calendar_mcp"
    assert path_item.post.security == [{"BearerAuth": []}]
    assert path_item.post.responses is not None
    assert set(path_item.post.responses) == {"200", "401", "403"}
    assert path_item.post.parameters is not None
    parameters = [
        parameter
        for parameter in path_item.post.parameters
        if isinstance(parameter, Parameter)
    ]
    assert {parameter.name for parameter in parameters} == {
        "MCP-Method",
        "MCP-Protocol-Version",
    }

    assert document.components is not None
    assert document.components.schemas is not None
    assert "HTTPValidationError" not in document.components.schemas
    assert "ValidationError" not in document.components.schemas
    assert document.components.securitySchemes is not None
    raw_security_scheme = document.components.securitySchemes["BearerAuth"]
    security_scheme = HTTPBearer.model_validate(
        raw_security_scheme.model_dump(mode="json", by_alias=True)
    )
    assert security_scheme.scheme == "bearer"

    serialized_document = openapi_response.text
    assert "127.0.0.1:9" not in serialized_document
    assert "identity.example" not in serialized_document
    assert swagger_response.status_code == 200
    assert "/openapi.json" in swagger_response.text
    assert scalar_response.status_code == 200
    assert "/openapi.json" in scalar_response.text
    assert redoc_response.status_code == 404


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
