from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Literal, Protocol, cast

from fastapi import HTTPException, Request, Response, status
from fastmcp.server.auth import AuthProvider

from proxy.providers import (
    KeycloakAuthProviderConfig,
    load_auth_provider,
)
from proxy.settings import AdminConfig

logger = logging.getLogger(__name__)

ADMIN_SESSION_COOKIE: str = "admin_token"


CookieSameSite = Literal["strict", "lax", "none"]


def request_is_secure(request: Request) -> bool:
    """Whether the request arrived over TLS, honoring proxy-forwarded schemes."""

    forwarded = request.headers.get("x-forwarded-proto", "")
    scheme = forwarded.split(",")[0].strip() if forwarded else request.url.scheme
    return scheme.lower() == "https"


def set_admin_session_cookie(
    response: Response,
    token: str,
    *,
    secure: bool,
    samesite: CookieSameSite,
) -> None:
    """Persist the admin token in an HttpOnly session cookie.

    ``samesite="none"`` is only honored by browsers together with ``Secure``,
    so the cookie is marked secure whenever that policy is chosen.
    """

    response.set_cookie(
        ADMIN_SESSION_COOKIE,
        token,
        path="/",
        secure=secure or samesite == "none",
        httponly=True,
        samesite=samesite,
    )


def clear_admin_session_cookie(response: Response) -> None:
    """Drop the admin session cookie."""

    response.delete_cookie(ADMIN_SESSION_COOKIE, path="/")


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


def _bearer_token(request: Request) -> str | None:
    authorization = request.headers.get("Authorization", "")
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token.strip():
        return None
    return token.strip()


def _session_token(request: Request) -> str | None:
    token = request.cookies.get(ADMIN_SESSION_COOKIE)
    return token.strip() if token and token.strip() else None


def _origin_allowed(request: Request) -> bool:
    """Whether a browser-sent Origin may submit state-changing cookie requests.

    Guards cookie-authenticated mutations against cross-site request forgery
    when the cookie policy is ``SameSite=None``. Requests without an Origin
    header are treated as non-browser clients and allowed.
    """

    origin = request.headers.get("origin")
    if origin is None:
        return True
    settings = request.app.state.config
    allowed = {str(cors_origin).rstrip("/") for cors_origin in settings.cors_origins}
    allowed.add(str(settings.public_base_url).rstrip("/"))
    return origin.rstrip("/") in allowed


async def require_admin(request: Request) -> None:
    """Reject requests whose bearer token or session cookie is not valid."""

    provider = get_admin_provider(request)
    bearer = _bearer_token(request)
    cookie = _session_token(request)
    token = bearer or cookie
    if token is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing bearer token.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if await provider.verify_token(token) is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired bearer token.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    admin = request.app.state.config.admin
    if (
        bearer is None
        and cookie is not None
        and request.method not in ("GET", "HEAD", "OPTIONS")
        and admin is not None
        and admin.session_cookie_samesite == "none"
        and not _origin_allowed(request)
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cross-site admin request rejected.",
        )
