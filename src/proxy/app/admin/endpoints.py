from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel, TypeAdapter

from proxy.app.admin.auth import (
    CookieSameSite,
    clear_admin_session_cookie,
    get_admin_provider,
    request_is_secure,
    require_admin,
    set_admin_session_cookie,
)
from proxy.auth_providers.repository import AuthProviderNotFound
from proxy.providers import ManagedAuthProviderConfig
from proxy.servers.manager import ServerManager
from proxy.servers.models import McpServerConfig
from proxy.servers.repository import ServerNameTaken, ServerNotFound
from proxy.servers.schemas import (
    ServerCreateRequest,
    ServerUpdateRequest,
    ServerView,
)

router = APIRouter(
    prefix="/api/admin",
    tags=["admin"],
    dependencies=[Depends(require_admin)],
)

public_router = APIRouter(prefix="/api/admin", tags=["admin"])

AUTH_SCHEMA: dict = TypeAdapter(ManagedAuthProviderConfig).json_schema()


@public_router.get("/auth-status")
def auth_status(request: Request) -> dict:
    """Describe the admin identity provider for the sign-in screen.

    Authentication-free so the login page can decide how to present itself.
    ``oauth`` carries the authorization server issuer and public client the UI
    should use for a browser Authorization Code + PKCE flow, or None when only
    a pasted token is accepted.
    """

    provider = get_admin_provider(request)
    admin = request.app.state.config.admin
    flow = provider.oauth_browser_flow()
    return {
        "provider": admin.auth.provider,
        "oauth": (
            {"issuer": flow.issuer, "client_id": flow.client_id}
            if flow is not None
            else None
        ),
    }


@router.get("/me")
def me() -> dict[str, bool]:
    """Report whether the caller holds a valid admin token."""

    return {"authenticated": True}


class LoginRequest(BaseModel):
    username: str
    password: str


def _cookie_policy(request: Request) -> CookieSameSite:
    admin = request.app.state.config.admin
    return admin.session_cookie_samesite


@public_router.post("/login")
async def login(payload: LoginRequest, request: Request, response: Response) -> dict:
    """Resolve admin credentials to a session.

    Only providers that hold credentials themselves (``static``) support this;
    OAuth and token-verifier providers return 401. On success the bearer token
    is stored in an HttpOnly session cookie so the browser UI never persists
    it; the token stays in the response for non-browser API clients.
    """

    provider = get_admin_provider(request)
    token = await provider.login(payload.username, payload.password)
    if token is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password.",
        )
    set_admin_session_cookie(
        response,
        token,
        secure=request_is_secure(request),
        samesite=_cookie_policy(request),
    )
    return {"token": token}


class SessionRequest(BaseModel):
    token: str


@public_router.post("/session")
async def establish_session(
    payload: SessionRequest,
    request: Request,
    response: Response,
) -> dict:
    """Adopt a browser-flow or pasted bearer token into the session cookie.

    The browser Authorization Code + PKCE flow and the pasted-token flow
    terminate in JavaScript, so the UI hands the resulting token back to the
    gateway, which verifies it and stores it in an HttpOnly cookie.
    """

    provider = get_admin_provider(request)
    if await provider.verify_token(payload.token) is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired bearer token.",
        )
    set_admin_session_cookie(
        response,
        payload.token,
        secure=request_is_secure(request),
        samesite=_cookie_policy(request),
    )
    return {"authenticated": True}


@public_router.delete("/session", status_code=status.HTTP_204_NO_CONTENT)
async def end_session(response: Response) -> None:
    """Clear the admin session cookie."""

    clear_admin_session_cookie(response)


@router.get("/auth-schema")
def auth_schema() -> dict:
    """Serve the JSON schema for every supported auth provider."""

    return AUTH_SCHEMA


def get_server_manager(request: Request) -> ServerManager:
    return request.app.state.server_manager


def _to_view(config: McpServerConfig) -> ServerView:
    return ServerView(
        name=config.name,
        description=config.description,
        upstream_url=str(config.upstream_url),
        auth_provider=config.auth_provider,
        verify_upstream_tls=config.verify_upstream_tls,
        forward_client_credentials=config.forward_client_credentials,
    )


def _new_config(
    name: str,
    payload: ServerCreateRequest | ServerUpdateRequest,
) -> McpServerConfig:
    return McpServerConfig.model_validate(
        {
            "name": name,
            "description": payload.description,
            "upstream_url": payload.upstream_url,
            "auth_provider": payload.auth_provider,
            "verify_upstream_tls": payload.verify_upstream_tls,
            "forward_client_credentials": payload.forward_client_credentials,
        }
    )


def _updated_config(
    current: McpServerConfig,
    payload: ServerUpdateRequest,
) -> McpServerConfig:
    return McpServerConfig(
        name=current.name,
        description=payload.description,
        upstream_url=payload.upstream_url,
        auth_provider=payload.auth_provider,
        verify_upstream_tls=payload.verify_upstream_tls,
        forward_client_credentials=payload.forward_client_credentials,
    )


@router.get("/servers", response_model=list[ServerView])
def list_servers(request: Request) -> list[ServerView]:
    """Return the currently mounted servers."""

    manager = get_server_manager(request)
    return [_to_view(config) for config in manager.snapshot()]


def _invalid_config(error: Exception) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        detail=str(error),
    )


@router.post(
    "/servers",
    response_model=ServerView,
    status_code=status.HTTP_201_CREATED,
)
async def create_server(
    payload: ServerCreateRequest,
    request: Request,
) -> ServerView:
    """Create and live-mount a server."""

    manager = get_server_manager(request)
    try:
        config = _new_config(payload.name, payload)
        created = await manager.create(config)
    except AuthProviderNotFound as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(error),
        ) from error
    except ServerNameTaken as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(error),
        ) from error
    except (ValueError, KeyError) as error:
        raise _invalid_config(error) from error
    return _to_view(created)


@router.put("/servers/{name}", response_model=ServerView)
async def update_server(
    name: str,
    payload: ServerUpdateRequest,
    request: Request,
) -> ServerView:
    """Replace a server's definition live; the name is immutable."""

    manager = get_server_manager(request)
    try:
        current = manager.get(name)
        if current is None:
            raise ServerNotFound(f"Unknown MCP server '{name}'.")
        config = _updated_config(current, payload)
        updated = await manager.update(name, config)
    except AuthProviderNotFound as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(error),
        ) from error
    except ServerNotFound as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(error),
        ) from error
    except (TypeError, ValueError, KeyError) as error:
        raise _invalid_config(error) from error
    return _to_view(updated)


@router.delete("/servers/{name}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_server(name: str, request: Request) -> None:
    """Unmount and delete a server."""

    manager = get_server_manager(request)
    try:
        await manager.delete(name)
    except ServerNotFound as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(error),
        ) from error
