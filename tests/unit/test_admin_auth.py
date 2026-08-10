from __future__ import annotations


import pytest
from fastapi.testclient import TestClient
from starlette.routing import Route

import proxy.app.admin.auth as admin_auth_module
import proxy.servers.app as servers_app_module
from proxy.app.main import create_app
from proxy.providers import AuthProviderConfig
from proxy.servers.models import McpServerConfig
from proxy.settings import GatewayConfig
from tests.integration.helpers import seed_servers
from tests.support import StaticAuthProvider


@pytest.fixture()
def sqlite_url(tmp_path) -> str:
    return f"sqlite+aiosqlite:///{tmp_path / 'gateway.db'}"


@pytest.fixture()
def admin_config(sqlite_url: str) -> GatewayConfig:
    return GatewayConfig.model_validate(
        {
            "public_base_url": "https://gateway.example",
            "database": {"url": sqlite_url},
            "admin": {
                "auth": {
                    "provider": "keycloak",
                    "realm_url": "https://identity.example/realms/test",
                }
            },
        }
    )


@pytest.fixture()
def use_static_admin_provider(monkeypatch: pytest.MonkeyPatch) -> None:
    def load_static_provider(
        _config: AuthProviderConfig,
        *,
        base_url: str,
    ) -> StaticAuthProvider:
        return StaticAuthProvider(base_url=base_url)

    monkeypatch.setattr(
        admin_auth_module,
        "build_keycloak_admin_provider",
        lambda _config, *, base_url: None,
    )
    monkeypatch.setattr(admin_auth_module, "load_auth_provider", load_static_provider)
    monkeypatch.setattr(servers_app_module, "load_auth_provider", load_static_provider)


def boot(admin_config: GatewayConfig) -> TestClient:
    return TestClient(create_app(admin_config))


def test_me_authenticates_valid_token(
    admin_config: GatewayConfig,
    use_static_admin_provider: None,
) -> None:
    with boot(admin_config) as client:
        response = client.get(
            "/api/admin/me", headers={"Authorization": "Bearer valid-token"}
        )

    assert response.status_code == 200
    assert response.json() == {"authenticated": True}


def test_me_rejects_missing_and_invalid_tokens(
    admin_config: GatewayConfig,
    use_static_admin_provider: None,
) -> None:
    with boot(admin_config) as client:
        missing = client.get("/api/admin/me")
        invalid = client.get(
            "/api/admin/me", headers={"Authorization": "Bearer wrong-token"}
        )
        bad_scheme = client.get(
            "/api/admin/me", headers={"Authorization": "Basic dXNlcjpwYXNz"}
        )

    assert missing.status_code == 401
    assert invalid.status_code == 401
    assert bad_scheme.status_code == 401


def test_admin_endpoints_return_503_when_not_configured(
    sqlite_url: str,
) -> None:
    config = GatewayConfig.model_validate({"database": {"url": sqlite_url}})
    with boot(config) as client:
        response = client.get(
            "/api/admin/me", headers={"Authorization": "Bearer valid-token"}
        )

    assert response.status_code == 503


def test_auth_status_describes_token_verifier_provider(
    admin_config: GatewayConfig,
    use_static_admin_provider: None,
) -> None:
    with boot(admin_config) as client:
        response = client.get("/api/admin/auth-status")

    assert response.status_code == 200
    assert response.json() == {"provider": "keycloak", "oauth": False}


def test_auth_status_describes_oauth_hosting_provider(
    admin_config: GatewayConfig,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class OAuthHostingProvider(StaticAuthProvider):
        def get_routes(self, mcp_path: str | None = None) -> list[Route]:
            async def authorize(request: object) -> None:
                return None

            return [
                Route("/authorize", endpoint=authorize, methods=["GET"]),
                Route("/token", endpoint=authorize, methods=["POST"]),
            ]

    def load_oauth_provider(
        _config: AuthProviderConfig,
        *,
        base_url: str,
    ) -> OAuthHostingProvider:
        return OAuthHostingProvider(base_url=base_url)

    monkeypatch.setattr(admin_auth_module, "load_auth_provider", load_oauth_provider)
    monkeypatch.setattr(servers_app_module, "load_auth_provider", load_oauth_provider)

    with boot(admin_config) as client:
        response = client.get("/api/admin/auth-status")

    assert response.status_code == 200
    assert response.json() == {"provider": "keycloak", "oauth": True}


def test_auth_status_returns_503_when_not_configured(sqlite_url: str) -> None:
    config = GatewayConfig.model_validate({"database": {"url": sqlite_url}})
    with boot(config) as client:
        response = client.get("/api/admin/auth-status")

    assert response.status_code == 503


class RoutedStaticProvider(StaticAuthProvider):
    """Static provider that also advertises a well-known discovery route."""

    def get_routes(self, mcp_path: str | None = None) -> list[Route]:
        from starlette.responses import JSONResponse

        async def metadata(request: object) -> JSONResponse:
            return JSONResponse({"issuer": "admin-oauth"})

        return [
            Route(
                "/.well-known/oauth-authorization-server",
                endpoint=metadata,
                methods=["GET"],
            )
        ]


def test_admin_oauth_routes_are_prefixed_and_do_not_collide(
    admin_config: GatewayConfig,
    sqlite_url: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def load_routed_provider(
        _config: AuthProviderConfig,
        *,
        base_url: str,
    ) -> RoutedStaticProvider:
        return RoutedStaticProvider(base_url=base_url)

    monkeypatch.setattr(
        admin_auth_module,
        "build_keycloak_admin_provider",
        lambda _config, *, base_url: None,
    )
    monkeypatch.setattr(admin_auth_module, "load_auth_provider", load_routed_provider)
    monkeypatch.setattr(servers_app_module, "load_auth_provider", load_routed_provider)
    seed_servers(
        sqlite_url,
        [
            McpServerConfig.model_validate(
                {
                    "name": "calendar",
                    "upstream_url": "http://127.0.0.1:9/mcp",
                    "auth": {
                        "provider": "keycloak",
                        "realm_url": "https://identity.example/realms/test",
                    },
                }
            )
        ],
    )

    with boot(admin_config) as client:
        prefixed = client.get("/admin/oauth/.well-known/oauth-authorization-server")
        server_route = client.get("/.well-known/oauth-authorization-server")

    assert prefixed.status_code == 200
    assert prefixed.json() == {"issuer": "admin-oauth"}
    assert server_route.status_code == 200
