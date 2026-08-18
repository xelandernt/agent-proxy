from __future__ import annotations

import httpx2
import pytest
from fastapi.testclient import TestClient
from fastmcp.client.transports import StreamableHttpTransport
from pydantic import BaseModel, ConfigDict

import proxy.servers.app as servers_app_module
from proxy.app.main import create_app
from proxy.auth_providers.models import AuthProviderDefinition
from proxy.providers import KeycloakAuthProviderConfig
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


def keycloak_access_token(realm_url: str) -> str:
    with httpx2.Client(timeout=10) as client:
        response = client.post(
            f"{realm_url}/protocol/openid-connect/token",
            data={
                "grant_type": "password",
                "client_id": "mcp",
                "username": "user",
                "password": "password",
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
            "auth_provider": "keycloak",
        }
    )


def boot_keycloak_gateway(
    keycloak_realm_url: str,
    postgresql_url: str,
    postgresql: dict[str, object],
) -> TestClient:
    provider = AuthProviderDefinition(
        name="keycloak",
        auth=KeycloakAuthProviderConfig(
            provider="keycloak",
            realm_url=keycloak_realm_url,
            audience=RESOURCE_AUDIENCE,
            required_scopes=["openid"],
        ),
    )
    seed_servers(
        postgresql_url,
        [keycloak_server_config(keycloak_realm_url)],
        [provider],
    )
    config = GatewayConfig.model_validate(
        {
            "public_base_url": "https://gateway.example",
            "postgresql": postgresql,
            "admin": {"auth": {"provider": "static"}},
            "user": {
                "auth": {
                    "provider": "jwt",
                    "public_key": "test-user-auth-secret",
                    "algorithm": "HS256",
                }
            },
            "model_gateway": {
                "credential_encryption_key": (
                    "Zop6ZBEB1OB1D8SfORA4msZDzY1hEvqCnpF2DGpxs-E="
                )
            },
        }
    )
    return TestClient(create_app(config))


def test_keycloak_token_authenticates_without_reaching_upstream(
    keycloak_realm_url: str,
    postgresql_url: str,
    postgresql: dict[str, object],
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

    with boot_keycloak_gateway(
        keycloak_realm_url, postgresql_url, postgresql
    ) as client:
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
    postgresql_url: str,
    postgresql: dict[str, object],
) -> None:
    with boot_keycloak_gateway(
        keycloak_realm_url, postgresql_url, postgresql
    ) as client:
        response = client.get("/.well-known/oauth-protected-resource/calendar/mcp")

    assert response.status_code == 200
    assert response.json()["authorization_servers"] == [keycloak_realm_url]
