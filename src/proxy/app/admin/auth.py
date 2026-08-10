from __future__ import annotations

import logging
from typing import Protocol

from fastapi import HTTPException, Request, status
from fastapi.routing import BaseRoute
from starlette.routing import Route

from proxy.app.admin.oauth import KeycloakAdminOAuthProvider
from proxy.providers import (
    KeycloakAuthProviderConfig,
    load_auth_provider,
)
from proxy.settings import AdminConfig

logger = logging.getLogger(__name__)

ADMIN_OAUTH_PREFIX = "/admin/oauth"


class AdminAuthProvider(Protocol):
    """The subset of an identity provider the gateway's admin layer relies on."""

    def get_routes(self) -> list[Route]:
        """Provider routes mounted (unprefixed) under the admin OAuth prefix."""

    async def verify_token(self, token: str) -> object | None:
        """Verify a bearer token; return non-None when valid."""


def build_keycloak_admin_provider(
    config: KeycloakAuthProviderConfig,
    *,
    base_url: str,
) -> KeycloakAdminOAuthProvider | None:
    """Build the gateway-hosted Keycloak authorization server for the admin UI.

    Returns None when the provider cannot be constructed (for example the realm
    rejects dynamic client registration), letting the gateway fall back to
    token verification only.
    """

    try:
        return KeycloakAdminOAuthProvider.from_config(config, base_url=base_url)
    except Exception:
        logger.warning(
            "Admin OAuth browser sign-in is unavailable; falling back to token "
            "verification only.",
            exc_info=True,
        )
        return None


def build_admin_provider(
    admin: AdminConfig | None,
    public_base_url: str,
) -> AdminAuthProvider | None:
    """Construct the admin identity provider, or None when not configured."""

    if admin is None:
        return None
    base_url = f"{public_base_url.rstrip('/')}{ADMIN_OAUTH_PREFIX}"
    if admin.auth.provider == "keycloak":
        keycloak_provider = build_keycloak_admin_provider(
            admin.auth,
            base_url=base_url,
        )
        if keycloak_provider is not None:
            return keycloak_provider
    return load_auth_provider(admin.auth, base_url=base_url)


def admin_provider_routes(provider: AdminAuthProvider) -> list[BaseRoute]:
    """Return the provider's OAuth routes mounted under the admin prefix.

    Server apps already hoist ``/.well-known/*`` routes to the gateway root,
    so the admin provider must not claim the same paths. Anchoring its routes
    (and its advertised base URL) under ``/admin/oauth`` keeps discovery and
    callback URLs self-consistent and collision-free.
    """

    return [
        Route(
            path=f"{ADMIN_OAUTH_PREFIX}{route.path}",
            endpoint=route.endpoint,
            methods=route.methods,
            name=route.name,
            include_in_schema=False,
        )
        for route in provider.get_routes()
        if isinstance(route, Route) and isinstance(route.path, str)
    ]


def provider_hosts_oauth(provider: AdminAuthProvider) -> bool:
    """Whether the provider hosts an RFC 8414 authorization server on the gateway.

    OAuth-proxy providers expose an ``/authorize`` route; token-verifier
    providers (Keycloak, JWT, …) only advertise protected-resource metadata and
    cannot run a browser sign-in flow.
    """

    return any(
        isinstance(route, Route) and route.path == "/authorize"
        for route in provider.get_routes()
    )


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
