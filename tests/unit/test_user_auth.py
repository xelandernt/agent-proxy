from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from fastmcp.server.auth import AccessToken, AuthProvider

from proxy.app.admin.auth import AdminOAuthBrowserFlow
from proxy.app.dependencies import get_user_service
from proxy.app.main import create_app
from proxy.app.users import auth as user_auth
from proxy.app.users.auth import UserAuthProvider, UserIdentityError
from proxy.app.users.schemas import UserView
from proxy.app.users.service import UserAuthenticationError
from proxy.settings import GatewayConfig

REALM_URL = "https://identity.example/realms/test"
USER_ID = UUID("c8464904-f61b-48e3-9e87-ef0a1e15a05e")


class ClaimsProvider(AuthProvider):
    def __init__(self, claims: dict[str, object]) -> None:
        self._claims = claims

    async def verify_token(self, token: str) -> AccessToken | None:
        if token != "valid-token":
            return None
        return AccessToken(
            token=token,
            client_id="user-ui",
            subject="provider-subject",
            scopes=["openid", "email"],
            claims=self._claims,
        )


class FakeUserService:
    def __init__(self) -> None:
        now = datetime(2026, 8, 18, tzinfo=UTC)
        self.user = UserView(
            id=USER_ID,
            email="user@example.com",
            email_verified=True,
            display_name="Example User",
            created_at=now,
            last_login_at=now,
        )

    async def authenticate(self, token: str) -> UserView:
        if token != "valid-token":
            raise UserAuthenticationError("Invalid or expired bearer token.")
        return self.user

    async def login(self, username: str, password: str) -> tuple[str, UserView]:
        if (username, password) != ("user", "password"):
            raise UserAuthenticationError("Invalid username or password.")
        return "valid-token", self.user


def user_config(*, provider: str = "keycloak") -> GatewayConfig:
    auth: dict[str, object]
    if provider == "keycloak":
        auth = {
            "provider": "keycloak",
            "realm_url": REALM_URL,
            "client_id": "user-ui",
        }
    else:
        auth = {
            "provider": "jwt",
            "public_key": "test-key",
            "algorithm": "HS256",
        }
    return GatewayConfig.model_validate(
        {
            "public_base_url": "https://gateway.example",
            "admin": {"auth": {"provider": "static"}},
            "user": {"auth": auth},
            "model_gateway": {
                "credential_encryption_key": (
                    "Zop6ZBEB1OB1D8SfORA4msZDzY1hEvqCnpF2DGpxs-E="
                )
            },
        }
    )


def boot(config: GatewayConfig) -> TestClient:
    app = create_app(config)
    app.dependency_overrides[get_user_service] = FakeUserService
    return TestClient(app)


@pytest.mark.asyncio
async def test_user_provider_extracts_stable_identity_and_email() -> None:
    provider = UserAuthProvider(
        ClaimsProvider(
            {
                "iss": "https://identity.example/realms/test/",
                "sub": "ignored-in-favor-of-access-token-subject",
                "email": "user@example.com",
                "email_verified": True,
                "name": "Example User",
            }
        ),
        oauth_browser_flow=None,
    )

    principal = await provider.resolve_principal("valid-token")

    assert principal is not None
    assert principal.issuer == REALM_URL
    assert principal.subject == "provider-subject"
    assert principal.email == "user@example.com"
    assert principal.email_verified is True


@pytest.mark.asyncio
async def test_user_provider_requires_email() -> None:
    provider = UserAuthProvider(
        ClaimsProvider({"iss": REALM_URL, "sub": "provider-subject"}),
        oauth_browser_flow=None,
    )

    with pytest.raises(UserIdentityError, match="email claim"):
        await provider.resolve_principal("valid-token")


@pytest.mark.asyncio
async def test_userinfo_cannot_replace_verified_identity(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fake_userinfo(_issuer: str, _token: str) -> dict[str, object]:
        return {
            "iss": "https://attacker.example",
            "sub": "different-subject",
            "email": "user@example.com",
        }

    monkeypatch.setattr(user_auth, "_load_userinfo", fake_userinfo)
    provider = UserAuthProvider(
        ClaimsProvider({"iss": REALM_URL, "sub": "provider-subject"}),
        oauth_browser_flow=AdminOAuthBrowserFlow(
            issuer=REALM_URL,
            client_id="user-ui",
        ),
    )

    with pytest.raises(UserIdentityError, match="UserInfo subject"):
        await provider.resolve_principal("valid-token")


def test_user_auth_status_requests_openid_and_email() -> None:
    with boot(user_config(provider="keycloak")) as client:
        response = client.get("/api/user/auth-status")

    assert response.status_code == 200
    assert response.json() == {
        "provider": "keycloak",
        "oauth": {
            "issuer": REALM_URL,
            "client_id": "user-ui",
            "scopes": ["openid", "email"],
        },
    }


def test_user_login_sets_separate_http_only_cookie() -> None:
    with boot(user_config()) as client:
        response = client.post(
            "/api/user/login",
            json={"username": "user", "password": "password"},
        )

    assert response.status_code == 200
    assert response.cookies.get("user_token") == "valid-token"
    assert response.cookies.get("admin_token") is None
    assert "HttpOnly" in response.headers["set-cookie"]
    assert response.json()["user"]["email"] == "user@example.com"


def test_user_session_and_me_use_user_cookie() -> None:
    with boot(user_config()) as client:
        established = client.post("/api/user/session", json={"token": "valid-token"})
        current = client.get("/api/user/me")
        logout = client.delete("/api/user/session")
        after_logout = client.get("/api/user/me")

    assert established.status_code == 200
    assert current.status_code == 200
    assert current.json()["id"] == str(USER_ID)
    assert logout.status_code == 204
    assert after_logout.status_code == 401


def test_user_session_rejects_invalid_token() -> None:
    with boot(user_config()) as client:
        response = client.post("/api/user/session", json={"token": "wrong"})

    assert response.status_code == 401
    assert response.cookies.get("user_token") is None
