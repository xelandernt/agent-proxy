from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from proxy.app.admin.auth import require_admin
from proxy.app.dependencies import ModelProviderServiceDep
from proxy.model_providers.repository import (
    ModelProviderInUse,
    ModelProviderNameTaken,
    ModelProviderNotFound,
)
from proxy.model_providers.schemas import (
    ModelProviderCreate,
    ModelProviderUpdate,
    ModelProviderView,
)
from proxy.model_providers.service import ModelProviderCredentialsMissing
from proxy.security.credentials import (
    CredentialEncryptionUnavailable,
    InvalidCredentialCiphertext,
)

router = APIRouter(
    prefix="/api/admin/model-providers",
    tags=["admin-model-providers"],
    dependencies=[Depends(require_admin)],
)


@router.get("", response_model=list[ModelProviderView])
async def list_model_providers(
    service: ModelProviderServiceDep,
) -> list[ModelProviderView]:
    return await service.list()


@router.post("", response_model=ModelProviderView, status_code=status.HTTP_201_CREATED)
async def create_model_provider(
    payload: ModelProviderCreate, service: ModelProviderServiceDep
) -> ModelProviderView:
    try:
        return await service.create(payload)
    except ModelProviderNameTaken as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    except ModelProviderCredentialsMissing as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    except CredentialEncryptionUnavailable as error:
        raise HTTPException(status_code=503, detail=str(error)) from error


@router.get("/{name}", response_model=ModelProviderView)
async def get_model_provider(
    name: str, service: ModelProviderServiceDep
) -> ModelProviderView:
    try:
        return await service.get(name)
    except ModelProviderNotFound as error:
        raise HTTPException(status_code=404, detail=str(error)) from error


@router.put("/{name}", response_model=ModelProviderView)
async def update_model_provider(
    name: str, payload: ModelProviderUpdate, service: ModelProviderServiceDep
) -> ModelProviderView:
    try:
        return await service.update(name, payload)
    except ModelProviderNotFound as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except ModelProviderCredentialsMissing as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    except CredentialEncryptionUnavailable as error:
        raise HTTPException(status_code=503, detail=str(error)) from error
    except InvalidCredentialCiphertext as error:
        raise HTTPException(
            status_code=500,
            detail="Stored model provider credentials could not be decrypted.",
        ) from error


@router.delete("/{name}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_model_provider(name: str, service: ModelProviderServiceDep) -> None:
    try:
        await service.delete(name)
    except ModelProviderNotFound as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except ModelProviderInUse as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
