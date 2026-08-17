from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

import proxy.servers.app as servers_app_module
from proxy.app.main import create_app
from proxy.providers import ManagedAuthProviderConfig
from proxy.servers.models import McpServerConfig
from proxy.settings import GatewayConfig
from tests.integration.helpers import seed_servers
from tests.integration.test_keycloak import keycloak_access_token
from tests.support import StaticAuthProvider

pytestmark = pytest.mark.integration

RESOURCE_AUDIENCE = "https://gateway.example/calendar/mcp"


@pytest.fixture(autouse=True)
def use_static_auth_provider(monkeypatch: pytest.MonkeyPatch) -> None:
    def load_static_provider(
        _config: ManagedAuthProviderConfig,
        *,
        base_url: str,
    ) -> StaticAuthProvider:
        return StaticAuthProvider(base_url=base_url, required_scopes=["mcp"])

    monkeypatch.setattr(servers_app_module, "load_auth_provider", load_static_provider)


def boot_admin_gateway(
    keycloak_realm_url: str,
    postgresql_url: str,
    postgresql: dict[str, object],
) -> TestClient:
    seed_servers(
        postgresql_url,
        [
            McpServerConfig.model_validate(
                {
                    "name": "calendar",
                    "upstream_url": "http://127.0.0.1:9/mcp",
                    "auth_provider": "keycloak",
                }
            )
        ],
    )
    config = GatewayConfig.model_validate(
        {
            "public_base_url": "https://gateway.example",
            "postgresql": postgresql,
            "admin": {
                "auth": {
                    "provider": "keycloak",
                    "realm_url": keycloak_realm_url,
                    "client_id": "admin",
                    "audience": RESOURCE_AUDIENCE,
                    "required_scopes": ["openid"],
                }
            },
        }
    )
    return TestClient(create_app(config))


def test_keycloak_token_grants_admin_access(
    keycloak_realm_url: str,
    postgresql_url: str,
    postgresql: dict[str, object],
) -> None:
    token = keycloak_access_token(keycloak_realm_url)

    with boot_admin_gateway(keycloak_realm_url, postgresql_url, postgresql) as client:
        accepted = client.get(
            "/api/admin/me", headers={"Authorization": f"Bearer {token}"}
        )
        rejected = client.get(
            "/api/admin/me", headers={"Authorization": "Bearer invalid-token"}
        )

    assert accepted.status_code == 200
    assert accepted.json() == {"authenticated": True}
    assert rejected.status_code == 401
