from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

import proxy.app.admin.auth as admin_auth_module
import proxy.servers.app as servers_app_module
from proxy.app.main import create_app
from proxy.providers import AuthProviderConfig
from proxy.settings import GatewayConfig
from tests.support import StaticAuthProvider

REALM_URL = "https://identity.example/realms/test"
UI_CLIENT_ID = "agent-proxy-admin-ui"
STATIC_USERNAME = "admin"
STATIC_PASSWORD = "hunter2"
STATIC_SECRET = "a-very-long-random-secret-at-least-32-bytes"


@pytest.fixture()
def sqlite_url(tmp_path) -> str:
    return f"sqlite+aiosqlite:///{tmp_path / 'gateway.db'}"


@pytest.fixture()
def static_config(sqlite_url: str) -> GatewayConfig:
    return GatewayConfig.model_validate(
        {
            "public_base_url": "https://gateway.example",
            "database": {"url": sqlite_url},
            "admin": {
                "auth": {
                    "provider": "static",
                    "username": STATIC_USERNAME,
                    "password": STATIC_PASSWORD,
                    "jwt_secret": STATIC_SECRET,
                }
            },
        }
    )


@pytest.fixture()
def keycloak_config(sqlite_url: str) -> GatewayConfig:
    return GatewayConfig.model_validate(
        {
            "public_base_url": "https://gateway.example",
            "database": {"url": sqlite_url},
            "admin": {
                "auth": {
                    "provider": "keycloak",
                    "realm_url": REALM_URL,
                    "client_id": UI_CLIENT_ID,
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

    monkeypatch.setattr(admin_auth_module, "load_auth_provider", load_static_provider)
    monkeypatch.setattr(servers_app_module, "load_auth_provider", load_static_provider)


def boot(config: GatewayConfig) -> TestClient:
    return TestClient(create_app(config))


def test_me_authenticates_valid_token(
    keycloak_config: GatewayConfig,
    use_static_admin_provider: None,
) -> None:
    with boot(keycloak_config) as client:
        response = client.get(
            "/api/admin/me", headers={"Authorization": "Bearer valid-token"}
        )

    assert response.status_code == 200
    assert response.json() == {"authenticated": True}


def test_me_rejects_missing_and_invalid_tokens(
    keycloak_config: GatewayConfig,
    use_static_admin_provider: None,
) -> None:
    with boot(keycloak_config) as client:
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


def test_admin_endpoints_return_503_when_not_configured(sqlite_url: str) -> None:
    config = GatewayConfig.model_validate({"database": {"url": sqlite_url}})
    with boot(config) as client:
        response = client.get(
            "/api/admin/me", headers={"Authorization": "Bearer valid-token"}
        )

    assert response.status_code == 503


def test_auth_status_describes_keycloak_browser_flow(
    keycloak_config: GatewayConfig,
) -> None:
    with boot(keycloak_config) as client:
        response = client.get("/api/admin/auth-status")

    assert response.status_code == 200
    assert response.json() == {
        "provider": "keycloak",
        "oauth": {"issuer": REALM_URL, "client_id": UI_CLIENT_ID},
    }


def test_auth_status_for_token_only_provider_is_null(sqlite_url: str) -> None:
    config = GatewayConfig.model_validate(
        {
            "public_base_url": "https://gateway.example",
            "database": {"url": sqlite_url},
            "admin": {
                "auth": {
                    "provider": "jwt",
                    "public_key": "test-public-key",
                    "algorithm": "HS256",
                }
            },
        }
    )
    with boot(config) as client:
        response = client.get("/api/admin/auth-status")

    assert response.status_code == 200
    assert response.json() == {"provider": "jwt", "oauth": None}


def test_auth_status_returns_503_when_not_configured(sqlite_url: str) -> None:
    config = GatewayConfig.model_validate({"database": {"url": sqlite_url}})
    with boot(config) as client:
        response = client.get("/api/admin/auth-status")

    assert response.status_code == 503


def test_auth_status_describes_static_password_provider(
    static_config: GatewayConfig,
) -> None:
    with boot(static_config) as client:
        response = client.get("/api/admin/auth-status")

    assert response.status_code == 200
    assert response.json() == {"provider": "static", "oauth": None}


def test_static_login_issues_verifiable_token(static_config: GatewayConfig) -> None:
    with boot(static_config) as client:
        login = client.post(
            "/api/admin/login",
            json={"username": STATIC_USERNAME, "password": STATIC_PASSWORD},
        )
        token = login.json()["token"]
        me = client.get("/api/admin/me", headers={"Authorization": f"Bearer {token}"})

    assert login.status_code == 200
    assert me.status_code == 200
    assert me.json() == {"authenticated": True}


def test_static_login_rejects_bad_credentials(static_config: GatewayConfig) -> None:
    with boot(static_config) as client:
        wrong_password = client.post(
            "/api/admin/login",
            json={"username": STATIC_USERNAME, "password": "nope"},
        )
        wrong_username = client.post(
            "/api/admin/login",
            json={"username": "nope", "password": STATIC_PASSWORD},
        )

    assert wrong_password.status_code == 401
    assert wrong_username.status_code == 401


def test_static_token_rejects_tampering(static_config: GatewayConfig) -> None:
    with boot(static_config) as client:
        login = client.post(
            "/api/admin/login",
            json={"username": STATIC_USERNAME, "password": STATIC_PASSWORD},
        )
        token = login.json()["token"]
        header, payload, signature = token.split(".")
        tampered = f"{header}.{payload}.{'A' * len(signature)}"
        me = client.get(
            "/api/admin/me", headers={"Authorization": f"Bearer {tampered}"}
        )

    assert login.status_code == 200
    assert me.status_code == 401


def test_static_auth_works_with_default_credentials(sqlite_url: str) -> None:
    config = GatewayConfig.model_validate(
        {
            "public_base_url": "https://gateway.example",
            "database": {"url": sqlite_url},
            "admin": {
                "auth": {
                    "provider": "static",
                }
            },
        }
    )
    with boot(config) as client:
        login = client.post(
            "/api/admin/login",
            json={"username": "user", "password": "password"},
        )
        token = login.json()["token"]
        me = client.get("/api/admin/me", headers={"Authorization": f"Bearer {token}"})

    assert login.status_code == 200
    assert me.status_code == 200


def test_login_unsupported_by_token_verifier_providers(
    keycloak_config: GatewayConfig,
) -> None:
    with boot(keycloak_config) as client:
        response = client.post(
            "/api/admin/login",
            json={"username": "admin", "password": "hunter2"},
        )

    assert response.status_code == 401
