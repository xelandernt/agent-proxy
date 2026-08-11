from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Protocol, cast

from fastapi import HTTPException, Request, status
from fastmcp.server.auth import AuthProvider

from proxy.providers import (
    KeycloakAuthProviderConfig,
    load_auth_provider,
)
from proxy.settings import AdminConfig

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class AdminOAuthBrowserFlow:
    """How the admin UI can run a browser Authorization Code + PKCE flow.

    The UI performs the flow directly against the identity provider's
    authorization server (``issuer``), acting as the pre-registered public
    client ``client_id``; the gateway backend only verifies the resulting
    bearer tokens.
    """

    issuer: str
    client_id: str


class AdminAuthProvider(Protocol):
    """The subset of an identity provider the gateway's admin layer relies on."""

    async def verify_token(self, token: str) -> object | None:
        """Verify a bearer token; return non-None when valid."""

    def oauth_browser_flow(self) -> AdminOAuthBrowserFlow | None:
        """Browser sign-in metadata, or None when only token verification works."""

    async def login(self, username: str, password: str) -> str | None:
        """Resolve username/password to a token, or None on bad credentials.

        Only password-capable providers (``static``) implement this; the rest
        always return None.
        """


class _AdminAuthProvider(AdminAuthProvider):
    """Adapter binding a provider to the admin browser-flow metadata."""

    def __init__(
        self,
        provider: AuthProvider,
        *,
        oauth_browser_flow: AdminOAuthBrowserFlow | None,
    ) -> None:
        self._provider = provider
        self._flow = oauth_browser_flow

    async def verify_token(self, token: str) -> object | None:
        return await self._provider.verify_token(token)

    def oauth_browser_flow(self) -> AdminOAuthBrowserFlow | None:
        return self._flow

    async def login(self, username: str, password: str) -> str | None:
        login = cast(
            Callable[[str, str], Awaitable[str | None]] | None,
            getattr(self._provider, "login", None),
        )
        if login is None:
            return None
        return await login(username, password)


def build_admin_provider(
    admin: AdminConfig | None,
    public_base_url: str,
) -> AdminAuthProvider | None:
    """Construct the admin identity provider, or None when not configured."""

    if admin is None:
        return None
    base_url = f"{public_base_url.rstrip('/')}/admin"
    oauth_browser_flow: AdminOAuthBrowserFlow | None = None
    if (
        isinstance(admin.auth, KeycloakAuthProviderConfig)
        and admin.auth.client_id is not None
    ):
        oauth_browser_flow = AdminOAuthBrowserFlow(
            issuer=str(admin.auth.realm_url),
            client_id=admin.auth.client_id,
        )
    try:
        provider = load_auth_provider(admin.auth, base_url=base_url)
    except Exception:
        logger.warning(
            "Admin authentication is unavailable; admin endpoints require a "
            "configured identity provider.",
            exc_info=True,
        )
        return None
    return _AdminAuthProvider(provider, oauth_browser_flow=oauth_browser_flow)


def get_admin_provider(request: Request) -> AdminAuthProvider:
    """Return the admin provider, or 503 when no admin section is configured."""

    provider: AdminAuthProvider | None = request.app.state.admin_provider
    if provider is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Admin interface is not configured.",
        )
    return provider


async def require_admin(request: Request) -> None:
    """Reject requests whose bearer token the admin provider cannot verify."""

    provider = get_admin_provider(request)
    authorization = request.headers.get("Authorization", "")
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token.strip():
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing bearer token.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if await provider.verify_token(token.strip()) is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired bearer token.",
            headers={"WWW-Authenticate": "Bearer"},
        )
