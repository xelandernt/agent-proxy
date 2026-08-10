from __future__ import annotations

from fastapi import HTTPException, Request, status
from fastapi.routing import BaseRoute
from fastmcp.server.auth import AuthProvider
from starlette.routing import Route

from proxy.providers import load_auth_provider
from proxy.settings import AdminConfig

ADMIN_OAUTH_PREFIX = "/admin/oauth"


def build_admin_provider(
    admin: AdminConfig | None,
    public_base_url: str,
) -> AuthProvider | None:
    """Construct the admin identity provider, or None when not configured."""

    if admin is None:
        return None
    base_url = f"{public_base_url.rstrip('/')}{ADMIN_OAUTH_PREFIX}"
    return load_auth_provider(admin.auth, base_url=base_url)


def admin_provider_routes(provider: AuthProvider) -> list[BaseRoute]:
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


def get_admin_provider(request: Request) -> AuthProvider:
    """Return the admin provider, or 503 when no admin section is configured."""

    provider: AuthProvider | None = request.app.state.admin_provider
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
