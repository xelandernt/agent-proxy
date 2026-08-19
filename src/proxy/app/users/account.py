from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, HTTPException, status

from proxy.api_keys.repository import ApiKeyModelNotFound, ApiKeyNotFound
from proxy.api_keys.schemas import ApiKeyCreate, ApiKeyCreated, ApiKeyUpdate, ApiKeyView
from proxy.app.dependencies import (
    ApiKeyServiceDep,
    CurrentUserDep,
    ModelDeploymentServiceDep,
)
from proxy.app.users.schemas import AvailableModelView

router = APIRouter(prefix="/api/user", tags=["user-account"])


@router.get("/models", response_model=list[AvailableModelView])
async def list_models(
    _user: CurrentUserDep,
    models: ModelDeploymentServiceDep,
) -> list[AvailableModelView]:
    return [AvailableModelView(name=model.name) for model in await models.list()]


@router.get("/api-keys", response_model=list[ApiKeyView])
async def list_api_keys(
    user: CurrentUserDep,
    keys: ApiKeyServiceDep,
) -> list[ApiKeyView]:
    return await keys.list_for_user(user.id)


@router.post(
    "/api-keys", response_model=ApiKeyCreated, status_code=status.HTTP_201_CREATED
)
async def create_api_key(
    payload: ApiKeyCreate,
    user: CurrentUserDep,
    keys: ApiKeyServiceDep,
) -> ApiKeyCreated:
    try:
        return await keys.create(user.id, payload)
    except ApiKeyModelNotFound as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


@router.patch("/api-keys/{key_id}", response_model=ApiKeyView)
async def update_api_key(
    key_id: UUID,
    payload: ApiKeyUpdate,
    user: CurrentUserDep,
    keys: ApiKeyServiceDep,
) -> ApiKeyView:
    try:
        return await keys.update(key_id, user.id, payload)
    except ApiKeyNotFound as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except ApiKeyModelNotFound as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


@router.delete("/api-keys/{key_id}", status_code=status.HTTP_204_NO_CONTENT)
async def revoke_api_key(
    key_id: UUID,
    user: CurrentUserDep,
    keys: ApiKeyServiceDep,
) -> None:
    try:
        await keys.revoke(key_id, user.id)
    except ApiKeyNotFound as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
