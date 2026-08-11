from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, TypeAdapter

from proxy.app.admin.auth import get_admin_provider, require_admin
from proxy.providers import AuthProviderConfig, AuthProviderLoadError
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

AUTH_SCHEMA: dict = TypeAdapter(AuthProviderConfig).json_schema()


@public_router.get("/auth-status")
def auth_status(request: Request) -> dict:
    """Describe the admin identity provider for the sign-in screen.

    Authentication-free so the login page can decide how to present itself.
    ``oauth`` carries the authorization server issuer and public client the UI
    should use for a browser Authorization Code + PKCE flow, or None when only
    a pasted token is accepted.
    """

    provider = request.app.state.admin_provider
    if provider is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Admin interface is not configured.",
        )
    admin = request.app.state.config.admin
    flow = provider.oauth_browser_flow()
    return {
        "provider": admin.auth.provider if admin is not None else None,
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


@public_router.post("/login")
async def login(payload: LoginRequest, request: Request) -> dict:
    """Resolve admin credentials to a bearer token.

    Only providers that hold credentials themselves (``static``) support this;
    OAuth and token-verifier providers return 401.
    """

    provider = get_admin_provider(request)
    token = await provider.login(payload.username, payload.password)
    if token is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password.",
        )
    return {"token": token}


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
        auth=config.auth,
        verify_upstream_tls=config.verify_upstream_tls,
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
            "auth": payload.auth,
            "verify_upstream_tls": payload.verify_upstream_tls,
        }
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
    config = _new_config(payload.name, payload)
    try:
        created = await manager.create(config)
    except ServerNameTaken as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(error),
        ) from error
    except AuthProviderLoadError as error:
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
    config = _new_config(name, payload)
    try:
        updated = await manager.update(name, config)
    except ServerNotFound as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(error),
        ) from error
    except ValueError as error:
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
