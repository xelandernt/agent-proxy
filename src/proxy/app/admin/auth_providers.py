from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, status

from proxy.app.admin.auth import require_admin
from proxy.auth_providers.models import AuthProviderDefinition
from proxy.auth_providers.repository import (
    AuthProviderInUse,
    AuthProviderNameTaken,
    AuthProviderNotFound,
)
from proxy.auth_providers.schemas import (
    AuthProviderCreateRequest,
    AuthProviderUpdateRequest,
    AuthProviderView,
    to_view,
)
from proxy.servers.manager import ServerManager

router = APIRouter(
    prefix="/api/admin/auth-providers",
    tags=["admin"],
    dependencies=[Depends(require_admin)],
)


def get_manager(request: Request) -> ServerManager:
    return request.app.state.server_manager


@router.get("", response_model=list[AuthProviderView])
async def list_auth_providers(request: Request) -> list[AuthProviderView]:
    manager = get_manager(request)
    definitions = await manager.list_auth_providers()
    return [to_view(definition) for definition in definitions]


@router.post("", response_model=AuthProviderView, status_code=status.HTTP_201_CREATED)
async def create_auth_provider(
    payload: AuthProviderCreateRequest,
    request: Request,
) -> AuthProviderView:
    try:
        definition = await get_manager(request).create_auth_provider(
            AuthProviderDefinition.model_validate(payload.model_dump())
        )
    except AuthProviderNameTaken as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    return to_view(definition)


@router.put("/{name}", response_model=AuthProviderView)
async def update_auth_provider(
    name: str,
    payload: AuthProviderUpdateRequest,
    request: Request,
) -> AuthProviderView:
    try:
        definition = await get_manager(request).update_auth_provider(name, payload.auth)
    except AuthProviderNotFound as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except (TypeError, ValueError) as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    return to_view(definition)


@router.delete("/{name}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_auth_provider(name: str, request: Request) -> None:
    try:
        await get_manager(request).delete_auth_provider(name)
    except AuthProviderNotFound as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except AuthProviderInUse as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
