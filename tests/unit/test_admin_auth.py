from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

import proxy.app.admin.auth as admin_auth_module
import proxy.servers.app as servers_app_module
from proxy.app.main import create_app
from proxy.settings import GatewayConfig
from tests.support import StaticAuthProvider

REALM_URL = "https://identity.example/realms/test"
UI_CLIENT_ID = "admin"
COGNITO_ISSUER = "https://cognito-idp.eu-central-1.amazonaws.com/eu-central-1_test"
COGNITO_CLIENT_ID = "cognito-admin"
STATIC_USERNAME = "admin"
STATIC_PASSWORD = "hunter2"
STATIC_SECRET = "a-very-long-random-secret-at-least-32-bytes"


@pytest.fixture()
def static_config() -> GatewayConfig:
    return GatewayConfig.model_validate(
        {
            "public_base_url": "https://gateway.example",
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
def keycloak_config() -> GatewayConfig:
    return GatewayConfig.model_validate(
        {
            "public_base_url": "https://gateway.example",
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
def cognito_config() -> GatewayConfig:
    return GatewayConfig.model_validate(
        {
            "public_base_url": "https://gateway.example",
            "admin": {
                "auth": {
                    "provider": "aws-cognito",
                    "user_pool_id": "eu-central-1_test",
                    "client_id": COGNITO_CLIENT_ID,
                    "aws_region": "eu-central-1",
                }
            },
        }
    )


@pytest.fixture()
def use_static_admin_provider(monkeypatch: pytest.MonkeyPatch) -> None:
    def load_static_provider(
        _config: object,
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


def test_admin_endpoints_return_503_when_not_configured() -> None:
    config = GatewayConfig.model_validate({})
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


def test_auth_status_describes_cognito_browser_flow(
    cognito_config: GatewayConfig,
) -> None:
    with boot(cognito_config) as client:
        response = client.get("/api/admin/auth-status")

    assert response.status_code == 200
    assert response.json() == {
        "provider": "aws-cognito",
        "oauth": {"issuer": COGNITO_ISSUER, "client_id": COGNITO_CLIENT_ID},
    }


def test_auth_status_for_token_only_provider_is_null() -> None:
    config = GatewayConfig.model_validate(
        {
            "public_base_url": "https://gateway.example",
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


def test_auth_status_returns_503_when_not_configured() -> None:
    config = GatewayConfig.model_validate({})
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


def test_static_auth_works_with_default_credentials() -> None:
    config = GatewayConfig.model_validate(
        {
            "public_base_url": "https://gateway.example",
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


def test_static_login_sets_http_only_session_cookie(
    static_config: GatewayConfig,
) -> None:
    with boot(static_config) as client:
        login = client.post(
            "/api/admin/login",
            json={"username": STATIC_USERNAME, "password": STATIC_PASSWORD},
        )
        cookie = login.cookies.get("admin_token")
        me = client.get("/api/admin/me")

    assert login.status_code == 200
    assert cookie is not None
    assert "HttpOnly" in login.headers["set-cookie"]
    assert me.status_code == 200
    assert me.json() == {"authenticated": True}


def test_session_endpoint_adopts_token_into_cookie(
    keycloak_config: GatewayConfig,
    use_static_admin_provider: None,
) -> None:
    with boot(keycloak_config) as client:
        adopted = client.post("/api/admin/session", json={"token": "valid-token"})
        me = client.get("/api/admin/me")

    assert adopted.status_code == 200
    assert adopted.cookies.get("admin_token") == "valid-token"
    assert me.status_code == 200


def test_session_endpoint_rejects_invalid_token(
    keycloak_config: GatewayConfig,
    use_static_admin_provider: None,
) -> None:
    with boot(keycloak_config) as client:
        rejected = client.post("/api/admin/session", json={"token": "wrong-token"})

    assert rejected.status_code == 401
    assert rejected.cookies.get("admin_token") is None


def test_logout_clears_session_cookie(
    static_config: GatewayConfig,
) -> None:
    with boot(static_config) as client:
        login = client.post(
            "/api/admin/login",
            json={"username": STATIC_USERNAME, "password": STATIC_PASSWORD},
        )
        logout = client.delete("/api/admin/session")
        me = client.get("/api/admin/me")

    assert login.status_code == 200
    assert logout.status_code == 204
    assert "admin_token=" in logout.headers["set-cookie"]
    assert me.status_code == 401


def test_cookie_mutation_blocks_cross_site_origin_when_samesite_none(
    use_static_admin_provider: None,
) -> None:
    config = GatewayConfig.model_validate(
        {
            "public_base_url": "https://gateway.example",
            "middleware": {"cors": {"origins": ["https://ui.example.com"]}},
            "admin": {
                "auth": {
                    "provider": "keycloak",
                    "realm_url": REALM_URL,
                    "client_id": UI_CLIENT_ID,
                },
                "session_cookie_samesite": "none",
            },
        }
    )
    with TestClient(create_app(config), base_url="https://testserver") as client:
        adopted = client.post(
            "/api/admin/session",
            json={"token": "valid-token"},
            headers={"Origin": "https://ui.example.com"},
        )
        blocked = client.post(
            "/api/admin/servers",
            json={},
            headers={"Origin": "https://evil.example"},
        )
        allowed = client.post(
            "/api/admin/servers",
            json={},
            headers={"Origin": "https://ui.example.com"},
        )

    assert adopted.status_code == 200
    assert blocked.status_code == 403
    assert allowed.status_code == 422  # authenticated, rejected on payload
