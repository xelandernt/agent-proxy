from __future__ import annotations

from typing import Any, cast

import httpx2
from fastapi import Request, Response
from fastmcp.server.auth import AccessToken

from proxy.app.admin.auth import (
    AdminAuthProvider,
    AdminOAuthBrowserFlow,
    CookieSameSite,
    request_is_secure,
)
from proxy.app.users.schemas import UserPrincipal
from proxy.providers import (
    AwsCognitoAdminAuthProviderConfig,
    KeycloakAuthProviderConfig,
    load_auth_provider,
)
from proxy.settings import UserConfig

USER_SESSION_COOKIE = "user_token"


class UserIdentityError(ValueError):
    """Raised when a verified token lacks required identity claims."""


class UserAuthProvider(AdminAuthProvider):
    """Interactive provider plus user identity resolution."""

    def __init__(
        self,
        provider: Any,
        *,
        oauth_browser_flow: AdminOAuthBrowserFlow | None,
    ) -> None:
        self._provider = provider
        self._flow = oauth_browser_flow

    async def verify_token(self, token: str) -> AccessToken | None:
        return cast(AccessToken | None, await self._provider.verify_token(token))

    def oauth_browser_flow(self) -> AdminOAuthBrowserFlow | None:
        return self._flow

    async def login(self, username: str, password: str) -> str | None:
        login = getattr(self._provider, "login", None)
        if login is None:
            return None
        return cast(str | None, await login(username, password))

    async def resolve_principal(self, token: str) -> UserPrincipal | None:
        access_token = await self.verify_token(token)
        if access_token is None:
            return None
        claims = dict(access_token.claims)
        if self._flow is not None and not claims.get("email"):
            userinfo = await _load_userinfo(self._flow.issuer, token)
            userinfo_subject = userinfo.get("sub")
            if (
                access_token.subject
                and isinstance(userinfo_subject, str)
                and userinfo_subject != access_token.subject
            ):
                raise UserIdentityError(
                    "The UserInfo subject does not match the token."
                )
            for name in ("email", "email_verified", "name", "preferred_username"):
                if name in userinfo:
                    claims[name] = userinfo[name]
        issuer = _required_claim(
            claims,
            "iss",
            fallback=self._flow.issuer if self._flow else None,
            max_length=2048,
        )
        subject = access_token.subject or _required_claim(claims, "sub", max_length=255)
        if len(subject) > 255:
            raise UserIdentityError(
                "The identity provider returned an invalid subject."
            )
        email = _required_claim(claims, "email", max_length=320)
        email_verified = claims.get("email_verified")
        if email_verified is not None and not isinstance(email_verified, bool):
            raise UserIdentityError(
                "The identity provider returned an invalid email_verified claim."
            )
        display_name = claims.get("name") or claims.get("preferred_username")
        if isinstance(display_name, str):
            display_name = display_name.strip()[:255] or None
        return UserPrincipal(
            issuer=issuer.rstrip("/"),
            subject=subject,
            email=email,
            email_verified=email_verified,
            display_name=display_name if isinstance(display_name, str) else None,
        )


def build_user_provider(
    user: UserConfig,
    public_base_url: str,
) -> UserAuthProvider:
    base_url = f"{public_base_url.rstrip('/')}/user"
    flow: AdminOAuthBrowserFlow | None = None
    if isinstance(user.auth, AwsCognitoAdminAuthProviderConfig):
        flow = AdminOAuthBrowserFlow(
            issuer=user.auth.resolved_issuer,
            client_id=user.auth.client_id,
        )
    elif (
        isinstance(user.auth, KeycloakAuthProviderConfig)
        and user.auth.client_id is not None
    ):
        flow = AdminOAuthBrowserFlow(
            issuer=str(user.auth.realm_url),
            client_id=user.auth.client_id,
        )
    provider = load_auth_provider(user.auth, base_url=base_url)
    return UserAuthProvider(provider, oauth_browser_flow=flow)


def get_user_provider(request: Request) -> UserAuthProvider:
    return cast(UserAuthProvider, request.app.state.user_provider)


def user_session_token(request: Request) -> str | None:
    authorization = request.headers.get("Authorization", "")
    scheme, _, bearer = authorization.partition(" ")
    if scheme.lower() == "bearer" and bearer.strip():
        return bearer.strip()
    cookie = request.cookies.get(USER_SESSION_COOKIE)
    return cookie.strip() if cookie and cookie.strip() else None


def set_user_session_cookie(
    response: Response,
    token: str,
    *,
    secure: bool,
    samesite: CookieSameSite,
) -> None:
    response.set_cookie(
        USER_SESSION_COOKIE,
        token,
        path="/",
        secure=secure or samesite == "none",
        httponly=True,
        samesite=samesite,
    )


def clear_user_session_cookie(response: Response) -> None:
    response.delete_cookie(USER_SESSION_COOKIE, path="/")


def user_cookie_policy(request: Request) -> CookieSameSite:
    user = request.app.state.config.user
    return user.session_cookie_samesite


def user_request_is_secure(request: Request) -> bool:
    return request_is_secure(request)


def _required_claim(
    claims: dict[str, Any],
    name: str,
    *,
    fallback: str | None = None,
    max_length: int | None = None,
) -> str:
    value = claims.get(name, fallback)
    if not isinstance(value, str) or not value.strip():
        raise UserIdentityError(
            f"The identity provider did not return a usable {name} claim."
        )
    normalized = value.strip()
    if max_length is not None and len(normalized) > max_length:
        raise UserIdentityError(
            f"The identity provider returned an invalid {name} claim."
        )
    return normalized


async def _load_userinfo(issuer: str, token: str) -> dict[str, Any]:
    discovery_url = f"{issuer.rstrip('/')}/.well-known/openid-configuration"
    try:
        async with httpx2.AsyncClient(timeout=10) as client:
            discovery = await client.get(discovery_url)
            discovery.raise_for_status()
            metadata = discovery.json()
            if not isinstance(metadata, dict):
                raise UserIdentityError("Invalid OpenID discovery document.")
            metadata_issuer = metadata.get("issuer")
            endpoint = metadata.get("userinfo_endpoint")
            if not isinstance(metadata_issuer, str) or metadata_issuer.rstrip(
                "/"
            ) != issuer.rstrip("/"):
                raise UserIdentityError("OpenID discovery issuer mismatch.")
            if not isinstance(endpoint, str) or not endpoint:
                raise UserIdentityError("The provider has no UserInfo endpoint.")
            response = await client.get(
                endpoint,
                headers={"Authorization": f"Bearer {token}"},
            )
            response.raise_for_status()
            payload = response.json()
    except UserIdentityError:
        raise
    except Exception as error:
        raise UserIdentityError("Could not load user identity claims.") from error
    if not isinstance(payload, dict):
        raise UserIdentityError("Invalid UserInfo response.")
    return payload
