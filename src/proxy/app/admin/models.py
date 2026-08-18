from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from proxy.app.admin.auth import require_admin
from proxy.app.dependencies import ModelDeploymentServiceDep
from proxy.model_deployments.repository import (
    ModelDeploymentNameTaken,
    ModelDeploymentNotFound,
    ModelDeploymentReferenced,
)
from proxy.model_deployments.schemas import (
    ModelDeploymentCreate,
    ModelDeploymentUpdate,
    ModelDeploymentView,
)
from proxy.security.credentials import (
    CredentialEncryptionUnavailable,
    InvalidCredentialCiphertext,
)

router = APIRouter(
    prefix="/api/admin/models",
    tags=["admin-models"],
    dependencies=[Depends(require_admin)],
)


@router.get("", response_model=list[ModelDeploymentView])
async def list_models(
    service: ModelDeploymentServiceDep,
) -> list[ModelDeploymentView]:
    return await service.list()


@router.post(
    "", response_model=ModelDeploymentView, status_code=status.HTTP_201_CREATED
)
async def create_model(
    payload: ModelDeploymentCreate,
    service: ModelDeploymentServiceDep,
) -> ModelDeploymentView:
    try:
        return await service.create(payload)
    except ModelDeploymentNameTaken as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    except CredentialEncryptionUnavailable as error:
        raise HTTPException(status_code=503, detail=str(error)) from error


@router.get("/{name}", response_model=ModelDeploymentView)
async def get_model(
    name: str,
    service: ModelDeploymentServiceDep,
) -> ModelDeploymentView:
    try:
        return await service.get(name)
    except ModelDeploymentNotFound as error:
        raise HTTPException(status_code=404, detail=str(error)) from error


@router.patch("/{name}", response_model=ModelDeploymentView)
async def update_model(
    name: str,
    payload: ModelDeploymentUpdate,
    service: ModelDeploymentServiceDep,
) -> ModelDeploymentView:
    try:
        return await service.update(name, payload)
    except ModelDeploymentNotFound as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except CredentialEncryptionUnavailable as error:
        raise HTTPException(status_code=503, detail=str(error)) from error
    except InvalidCredentialCiphertext as error:
        raise HTTPException(
            status_code=500,
            detail="Stored model credentials could not be decrypted.",
        ) from error


@router.delete("/{name}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_model(
    name: str,
    service: ModelDeploymentServiceDep,
) -> None:
    try:
        await service.delete(name)
    except ModelDeploymentNotFound as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except ModelDeploymentReferenced as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
