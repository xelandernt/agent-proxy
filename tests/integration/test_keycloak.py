from __future__ import annotations

import httpx2
import pytest
from fastapi.testclient import TestClient
from fastmcp.client.transports import StreamableHttpTransport
from pydantic import BaseModel, ConfigDict, TypeAdapter

import proxy.servers.app as servers_app_module
from proxy.app.main import create_app
from proxy.servers.models import McpServerConfig
from proxy.settings import GatewayConfig
from proxy.transport import create_upstream_transport
from tests.integration.helpers import seed_servers
from tests.integration.test_gateway import (
    FakeModernUpstream,
    modern_headers,
    modern_request,
)

pytestmark = pytest.mark.integration

RESOURCE_AUDIENCE = "https://gateway.example/calendar/mcp"


class TokenResponse(BaseModel):
    model_config = ConfigDict(extra="allow")

    access_token: str
    refresh_token: str
    refresh_expires_in: int


class KeycloakClientRepresentation(BaseModel):
    model_config = ConfigDict(extra="allow")

    clientId: str
    publicClient: bool
    standardFlowEnabled: bool
    redirectUris: list[str]
    webOrigins: list[str]
    attributes: dict[str, str]


def keycloak_access_token(realm_url: str) -> str:
    with httpx2.Client(timeout=10) as client:
        response = client.post(
            f"{realm_url}/protocol/openid-connect/token",
            data={
                "grant_type": "password",
                "client_id": "gateway-integration-test",
                "username": "testuser",
                "password": "password123",
                "scope": "openid offline_access",
            },
        )
    assert response.is_success, response.text
    token = TokenResponse.model_validate(response.json())
    assert token.refresh_expires_in == 0
    return token.access_token


def keycloak_server_config(realm_url: str) -> McpServerConfig:
    return McpServerConfig.model_validate(
        {
            "name": "calendar",
            "upstream_url": "http://upstream.internal/mcp",
            "auth": {
                "provider": "keycloak",
                "realm_url": realm_url,
                "audience": RESOURCE_AUDIENCE,
                "required_scopes": ["openid"],
            },
        }
    )


def boot_keycloak_gateway(
    keycloak_realm_url: str,
    postgres_url: str,
) -> TestClient:
    seed_servers(postgres_url, [keycloak_server_config(keycloak_realm_url)])
    config = GatewayConfig.model_validate(
        {
            "public_base_url": "https://gateway.example",
            "database": {"url": postgres_url},
        }
    )
    return TestClient(create_app(config))


def test_compose_example_user_can_request_offline_access(
    keycloak_realm_url: str,
) -> None:
    with httpx2.Client(timeout=10) as client:
        response = client.post(
            f"{keycloak_realm_url}/protocol/openid-connect/token",
            data={
                "grant_type": "password",
                "client_id": "example-client",
                "username": "example",
                "password": "example",
                "scope": "openid offline_access",
            },
        )

    assert response.status_code == 200, response.text
    token = TokenResponse.model_validate(response.json())
    assert token.access_token
    assert token.refresh_token
    assert token.refresh_expires_in == 0


def test_keycloak_has_browser_compatible_mcp_inspector_client(
    keycloak_realm_url: str,
) -> None:
    keycloak_base_url, separator, _ = keycloak_realm_url.partition("/realms/")
    if not separator:
        raise ValueError("Keycloak realm URL does not contain /realms/.")

    with httpx2.Client(timeout=10) as client:
        token_response = client.post(
            f"{keycloak_base_url}/realms/master/protocol/openid-connect/token",
            data={
                "grant_type": "password",
                "client_id": "admin-cli",
                "username": "admin",
                "password": "admin",
            },
        )
        assert token_response.status_code == 200, token_response.text
        admin_token = token_response.json()["access_token"]
        assert isinstance(admin_token, str)

        clients_response = client.get(
            f"{keycloak_base_url}/admin/realms/agent-proxy/clients",
            params={"clientId": "mcp-inspector"},
            headers={"Authorization": f"Bearer {admin_token}"},
        )

    assert clients_response.status_code == 200, clients_response.text
    clients = TypeAdapter(list[KeycloakClientRepresentation]).validate_json(
        clients_response.content
    )
    assert len(clients) == 1
    inspector = clients[0]
    assert inspector.clientId == "mcp-inspector"
    assert inspector.publicClient is True
    assert inspector.standardFlowEnabled is True
    assert inspector.redirectUris == [
        "http://localhost:6274/oauth/callback",
        "http://localhost:6274/oauth/callback/debug",
    ]
    assert inspector.webOrigins == ["http://localhost:6274"]
    assert inspector.attributes["pkce.code.challenge.method"] == "S256"


def test_keycloak_token_authenticates_without_reaching_upstream(
    keycloak_realm_url: str,
    postgres_url: str,
    monkeypatch: pytest.MonkeyPatch,
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
    token = keycloak_access_token(keycloak_realm_url)

    with boot_keycloak_gateway(keycloak_realm_url, postgres_url) as client:
        invalid_response = client.post(
            "/calendar/mcp",
            headers=modern_headers("tools/list")
            | {"Authorization": "Bearer invalid-token"},
            json=modern_request("tools/list"),
        )
        assert not upstream_requests
        response = client.post(
            "/calendar/mcp",
            headers=modern_headers("tools/list") | {"Authorization": f"Bearer {token}"},
            json=modern_request("tools/list"),
        )

    assert invalid_response.status_code == 401
    assert response.status_code == 200, response.text
    assert upstream_requests
    assert all("authorization" not in request for request in upstream_requests)


def test_keycloak_is_advertised_by_protected_resource_metadata(
    keycloak_realm_url: str,
    postgres_url: str,
) -> None:
    with boot_keycloak_gateway(keycloak_realm_url, postgres_url) as client:
        response = client.get("/.well-known/oauth-protected-resource/calendar/mcp")

    assert response.status_code == 200
    assert response.json()["authorization_servers"] == [keycloak_realm_url]
