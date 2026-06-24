from typing import Annotated

from fastapi import Depends, Header, HTTPException, Request, status

from proxy.auth.challenge import build_auth_challenge
from proxy.auth.models import (
    AuthenticatedPrincipal,
    InsufficientScopeError,
    InvalidTokenError,
    MissingTokenError,
)
from proxy.auth.providers import (
    AuthProvider,
    DisabledAuthProvider,
)
from proxy.app.runtime import RuntimeDep
from proxy.settings import ProxyConfig, ResolvedMcpServer

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------


def get_config(runtime: RuntimeDep) -> ProxyConfig:
    """Extract ProxyConfig from the app runtime.

    Args:
        runtime: The application runtime.

    Returns:
        The proxy configuration.
    """
    return runtime.config


ConfigDep = Annotated[ProxyConfig, Depends(get_config)]

# ---------------------------------------------------------------------------
# Server lookup
# ---------------------------------------------------------------------------


async def get_server(name: str, config: ConfigDep) -> ResolvedMcpServer:
    """Resolve an MCP server by name from the configuration.

    Args:
        name: The server name from the URL path parameter.
        config: The proxy configuration.

    Returns:
        The resolved MCP server with its group context.

    Raises:
        HTTPException 404: If no server with the given name is configured.
    """
    resolved_server = config.get_server(name)
    if resolved_server is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Unknown MCP server '{name}'.",
        )
    return resolved_server


ServerDep = Annotated[ResolvedMcpServer, Depends(get_server)]

# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------


async def get_auth_provider(server: ServerDep, runtime: RuntimeDep) -> AuthProvider:
    """Get the auth provider for a given server's group.

    Falls back to DisabledAuthProvider if the group has no configured auth.

    Args:
        server: The resolved MCP server.
        runtime: The application runtime containing auth provider registry.

    Returns:
        The auth provider for the server's group.
    """
    return runtime.auth_providers.get(server.group.name, DisabledAuthProvider())


AuthProviderDep = Annotated[AuthProvider, Depends(get_auth_provider)]


async def require_authenticated_principal(
    request: Request,
    server: ServerDep,
    auth_provider: AuthProviderDep,
    authorization: Annotated[str | None, Header(alias="Authorization")] = None,
) -> AuthenticatedPrincipal:
    """Authenticate and authorize the incoming request.

    Validates the bearer token against the server's auth provider, checks
    required scopes, and returns the authenticated principal.

    Args:
        request: The incoming HTTP request (used to build challenge URLs).
        server: The resolved MCP server being accessed.
        auth_provider: The auth provider for the server's group.
        authorization: The raw Authorization header value.

    Returns:
        The authenticated principal extracted from the bearer token.

    Raises:
        HTTPException 401: If the token is missing or invalid.
        HTTPException 403: If the token lacks required scopes.
    """
    authorization_scopes = server.group.authorization_scopes_for_server(server.server)
    resource_metadata_url = str(
        request.url_for("get_protected_resource_metadata", name=server.server.name)
    )

    try:
        return auth_provider.authenticate_request(
            authorization=authorization,
            group=server.group,
            server=server.server,
        )
    except MissingTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing bearer token.",
            headers={
                "WWW-Authenticate": build_auth_challenge(
                    resource_metadata_url=resource_metadata_url,
                    scopes=authorization_scopes,
                )
            },
        )
    except InvalidTokenError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(exc),
            headers={
                "WWW-Authenticate": build_auth_challenge(
                    resource_metadata_url=resource_metadata_url,
                    scopes=authorization_scopes,
                )
            },
        )
    except InsufficientScopeError:
        required_scopes = server.group.required_scopes_for_server(server.server)
        forbidden_challenge = build_auth_challenge(
            resource_metadata_url=resource_metadata_url,
            scopes=required_scopes,
            error="insufficient_scope",
            error_description="The token does not grant access to this MCP server.",
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access token is missing required scopes.",
            headers={"WWW-Authenticate": forbidden_challenge},
        )


PrincipalDep = Annotated[
    AuthenticatedPrincipal, Depends(require_authenticated_principal)
]
