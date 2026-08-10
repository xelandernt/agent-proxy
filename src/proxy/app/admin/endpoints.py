from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import TypeAdapter

from proxy.app.admin.auth import require_admin
from proxy.providers import AuthProviderConfig
from proxy.servers.manager import ServerManager
from proxy.servers.models import McpServerConfig
from proxy.servers.repository import ServerNotFound, ServerNameTaken
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

AUTH_SCHEMA: dict = TypeAdapter(AuthProviderConfig).json_schema()


@router.get("/me")
def me() -> dict[str, bool]:
    """Report whether the caller holds a valid admin token."""

    return {"authenticated": True}


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
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(error),
        ) from error
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
