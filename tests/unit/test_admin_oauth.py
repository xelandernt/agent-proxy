from __future__ import annotations

import time
from urllib.parse import parse_qs, urlparse

import pytest
from authlib.jose import JsonWebKey
from authlib.jose import jwt as authlib_jwt
from fastapi.testclient import TestClient

import proxy.app.admin.auth as admin_auth_module
import proxy.app.admin.oauth as admin_oauth_module
from proxy.app.admin.oauth import KeycloakAdminOAuthProvider, _s256
from proxy.app.main import create_app
from proxy.settings import GatewayConfig
from tests.support import StaticAuthProvider

REALM_URL = "https://identity.example/realms/test"
CLIENT_ID = "gateway-admin"
CLIENT_SECRET = "hunter2"
CALLBACK_URL = "https://gateway.example/admin/oauth/callback"
UI_CALLBACK_URL = "http://ui.example/admin/callback"


@pytest.fixture()
def sqlite_url(tmp_path) -> str:
    return f"sqlite+aiosqlite:///{tmp_path / 'gateway.db'}"


@pytest.fixture()
def oauth_config(sqlite_url: str) -> GatewayConfig:
    return GatewayConfig.model_validate(
        {
            "public_base_url": "https://gateway.example",
            "database": {"url": sqlite_url},
            "admin": {
                "auth": {
                    "provider": "keycloak",
                    "realm_url": REALM_URL,
                    "client_id": CLIENT_ID,
                    "client_secret": CLIENT_SECRET,
                    "required_scopes": ["openid"],
                }
            },
        }
    )


def boot(oauth_config: GatewayConfig) -> TestClient:
    return TestClient(create_app(oauth_config))


@pytest.fixture()
def rsa_key() -> JsonWebKey:
    return JsonWebKey.generate_key("RSA", 2048, is_private=True)


def keycloak_token(
    rsa_key: JsonWebKey,
    *,
    iss: str = REALM_URL,
    aud: str | list[str] | None = CLIENT_ID,
    azp: str | None = None,
    scope: str = "openid",
) -> str:
    claims: dict[str, object] = {
        "iss": iss,
        "exp": int(time.time()) + 3600,
        "scope": scope,
        "sub": "test-user",
    }
    if aud is not None:
        claims["aud"] = aud
    if azp is not None:
        claims["azp"] = azp
    return authlib_jwt.encode({"alg": "RS256"}, claims, rsa_key).decode()


def register_ui_client(client: TestClient) -> str:
    response = client.post(
        "/admin/oauth/register",
        json={
            "client_name": "agent-proxy-admin-ui",
            "redirect_uris": [UI_CALLBACK_URL],
            "grant_types": ["authorization_code"],
            "response_types": ["code"],
            "token_endpoint_auth_method": "none",
            "application_type": "web",
        },
    )
    assert response.status_code == 201
    return response.json()["client_id"]


def test_oauth_metadata_served_under_admin_prefix(oauth_config: GatewayConfig) -> None:
    with boot(oauth_config) as client:
        response = client.get("/admin/oauth/.well-known/oauth-authorization-server")

    assert response.status_code == 200
    metadata = response.json()
    assert metadata["issuer"] == "https://gateway.example/admin/oauth"
    assert metadata["authorization_endpoint"] == (
        "https://gateway.example/admin/oauth/authorize"
    )
    assert metadata["token_endpoint"] == "https://gateway.example/admin/oauth/token"
    assert metadata["registration_endpoint"] == (
        "https://gateway.example/admin/oauth/register"
    )
    assert "S256" in metadata["code_challenge_methods_supported"]


def test_auth_status_reports_oauth_hosting_keycloak(
    oauth_config: GatewayConfig,
) -> None:
    with boot(oauth_config) as client:
        response = client.get("/api/admin/auth-status")

    assert response.status_code == 200
    assert response.json() == {"provider": "keycloak", "oauth": True}


def test_authorize_rejects_unknown_clients_and_redirect_uris(
    oauth_config: GatewayConfig,
) -> None:
    with boot(oauth_config) as client:
        unknown = client.get(
            "/admin/oauth/authorize",
            params={
                "client_id": "nope",
                "redirect_uri": UI_CALLBACK_URL,
                "response_type": "code",
                "state": "abc",
            },
        )
        registered = client.post(
            "/admin/oauth/register",
            json={"redirect_uris": [UI_CALLBACK_URL]},
        ).json()["client_id"]
        wrong_uri = client.get(
            "/admin/oauth/authorize",
            params={
                "client_id": registered,
                "redirect_uri": "http://evil.example/callback",
                "response_type": "code",
                "state": "abc",
            },
        )

    assert unknown.status_code == 400
    assert wrong_uri.status_code == 400


def test_browser_flow_exchanges_pkce_code_for_keycloak_token(
    oauth_config: GatewayConfig,
    rsa_key: JsonWebKey,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    token = keycloak_token(rsa_key)
    with boot(oauth_config) as client:
        provider: KeycloakAdminOAuthProvider = client.app.state.admin_provider

        async def fake_exchange(_code: str) -> dict[str, object]:
            return {"access_token": token, "expires_in": 3600}

        async def fake_jwks() -> object:
            return JsonWebKey.import_key_set(
                {"keys": [rsa_key.as_dict(is_private=False)]}
            )

        monkeypatch.setattr(provider, "_exchange_keycloak_code", fake_exchange)
        monkeypatch.setattr(provider, "_fetch_jwks", fake_jwks)

        ui_client_id = register_ui_client(client)
        verifier = "abcdefghijklmnopqrstuvwxyz0123456789"
        challenge = _s256(verifier)
        state = "flow-state"

        authorize = client.get(
            "/admin/oauth/authorize",
            params={
                "client_id": ui_client_id,
                "redirect_uri": UI_CALLBACK_URL,
                "response_type": "code",
                "scope": "openid",
                "state": state,
                "code_challenge": challenge,
                "code_challenge_method": "S256",
            },
            follow_redirects=False,
        )
        assert authorize.status_code == 302
        upstream = urlparse(authorize.headers["location"])
        assert upstream.path == "/realms/test/protocol/openid-connect/auth"
        upstream_params = parse_qs(upstream.query)
        assert upstream_params["client_id"] == [CLIENT_ID]
        assert upstream_params["redirect_uri"] == [CALLBACK_URL]
        assert upstream_params["state"] == [state]
        assert "code_challenge" not in upstream_params

        callback = client.get(
            "/admin/oauth/callback",
            params={"code": "keycloak-code", "state": state},
            follow_redirects=False,
        )
        assert callback.status_code == 302
        callback_params = parse_qs(urlparse(callback.headers["location"]).query)
        assert urlparse(callback.headers["location"]).path == "/admin/callback"
        assert callback_params["state"] == [state]
        assert callback_params["client_id"] == [ui_client_id]
        gateway_code = callback_params["code"][0]

        exchanged = client.post(
            "/admin/oauth/token",
            data={
                "grant_type": "authorization_code",
                "code": gateway_code,
                "redirect_uri": UI_CALLBACK_URL,
                "client_id": ui_client_id,
                "code_verifier": verifier,
            },
        )
        assert exchanged.status_code == 200
        assert exchanged.json()["access_token"] == token

        me = client.get("/api/admin/me", headers={"Authorization": f"Bearer {token}"})
        assert me.status_code == 200
        assert me.json() == {"authenticated": True}

        reused = client.post(
            "/admin/oauth/token",
            data={
                "grant_type": "authorization_code",
                "code": gateway_code,
                "redirect_uri": UI_CALLBACK_URL,
                "client_id": ui_client_id,
                "code_verifier": verifier,
            },
        )
        assert reused.status_code == 400


def test_token_rejects_wrong_pkce_verifier(
    oauth_config: GatewayConfig,
    rsa_key: JsonWebKey,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with boot(oauth_config) as client:
        provider: KeycloakAdminOAuthProvider = client.app.state.admin_provider

        async def fake_exchange(_code: str) -> dict[str, object]:
            return {"access_token": keycloak_token(rsa_key), "expires_in": 3600}

        monkeypatch.setattr(provider, "_exchange_keycloak_code", fake_exchange)

        ui_client_id = register_ui_client(client)
        state = "flow-state"
        challenge = _s256("the-real-verifier")
        client.get(
            "/admin/oauth/authorize",
            params={
                "client_id": ui_client_id,
                "redirect_uri": UI_CALLBACK_URL,
                "response_type": "code",
                "state": state,
                "code_challenge": challenge,
                "code_challenge_method": "S256",
            },
            follow_redirects=False,
        )
        callback = client.get(
            "/admin/oauth/callback",
            params={"code": "keycloak-code", "state": state},
            follow_redirects=False,
        )
        gateway_code = parse_qs(urlparse(callback.headers["location"]).query)["code"][0]

        rejected = client.post(
            "/admin/oauth/token",
            data={
                "grant_type": "authorization_code",
                "code": gateway_code,
                "redirect_uri": UI_CALLBACK_URL,
                "client_id": ui_client_id,
                "code_verifier": "wrong-verifier",
            },
        )

    assert rejected.status_code == 400
    assert rejected.json()["error"] == "invalid_grant"


def test_verify_token_accepts_realm_tokens(
    oauth_config: GatewayConfig,
    rsa_key: JsonWebKey,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with boot(oauth_config) as client:
        provider: KeycloakAdminOAuthProvider = client.app.state.admin_provider

        async def fake_jwks() -> object:
            return JsonWebKey.import_key_set(
                {"keys": [rsa_key.as_dict(is_private=False)]}
            )

        monkeypatch.setattr(provider, "_fetch_jwks", fake_jwks)
        valid = keycloak_token(rsa_key)
        no_aud_own_azp = keycloak_token(rsa_key, aud=None, azp=CLIENT_ID)
        no_aud_foreign_azp = keycloak_token(rsa_key, aud=None, azp="other-client")
        wrong_issuer = keycloak_token(rsa_key, iss="https://evil.example/realms/x")
        missing_scope = keycloak_token(rsa_key, scope="email")

        accepted = client.get(
            "/api/admin/me", headers={"Authorization": f"Bearer {valid}"}
        )
        azp_accepted = client.get(
            "/api/admin/me",
            headers={"Authorization": f"Bearer {no_aud_own_azp}"},
        )
        azp_rejected = client.get(
            "/api/admin/me",
            headers={"Authorization": f"Bearer {no_aud_foreign_azp}"},
        )
        bad_issuer = client.get(
            "/api/admin/me", headers={"Authorization": f"Bearer {wrong_issuer}"}
        )
        bad_scope = client.get(
            "/api/admin/me", headers={"Authorization": f"Bearer {missing_scope}"}
        )

    assert accepted.status_code == 200
    assert azp_accepted.status_code == 200
    assert azp_rejected.status_code == 401
    assert bad_issuer.status_code == 401
    assert bad_scope.status_code == 401


def test_keycloak_provider_auto_registers_client_when_unconfigured(
    sqlite_url: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config = GatewayConfig.model_validate(
        {
            "public_base_url": "https://gateway.example",
            "database": {"url": sqlite_url},
            "admin": {
                "auth": {
                    "provider": "keycloak",
                    "realm_url": REALM_URL,
                }
            },
        }
    )

    monkeypatch.setattr(
        admin_oauth_module,
        "register_upstream_client",
        lambda realm_url, redirect_uri: ("auto-client", "auto-secret"),
    )

    with boot(config) as client:
        provider: KeycloakAdminOAuthProvider = client.app.state.admin_provider
        status = client.get("/api/admin/auth-status")

    assert provider.client_id == "auto-client"
    assert status.json() == {"provider": "keycloak", "oauth": True}


def test_keycloak_provider_falls_back_when_registration_fails(
    sqlite_url: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config = GatewayConfig.model_validate(
        {
            "public_base_url": "https://gateway.example",
            "database": {"url": sqlite_url},
            "admin": {
                "auth": {
                    "provider": "keycloak",
                    "realm_url": REALM_URL,
                }
            },
        }
    )

    def failing_registration(realm_url: str, redirect_uri: str) -> tuple[str, str]:
        raise RuntimeError("registration disabled")

    monkeypatch.setattr(
        admin_oauth_module,
        "register_upstream_client",
        failing_registration,
    )
    monkeypatch.setattr(
        admin_auth_module,
        "load_auth_provider",
        lambda _config, *, base_url: StaticAuthProvider(base_url=base_url),
    )

    with boot(config) as client:
        status = client.get("/api/admin/auth-status")

    assert status.status_code == 200
    assert status.json() == {"provider": "keycloak", "oauth": False}
