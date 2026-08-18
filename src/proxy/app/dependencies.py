from __future__ import annotations

from typing import Annotated

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import async_sessionmaker

from proxy.api_keys.repository import ApiKeyRepository
from proxy.api_keys.service import ApiKeyService
from proxy.app.inference.service import InferenceService
from proxy.app.model_usage.recorder import ModelUsageRecorder
from proxy.app.model_usage.repository import ModelUsageRepository
from proxy.app.model_usage.service import ModelUsageService
from proxy.app.users.auth import get_user_provider, user_session_token
from proxy.app.users.repository import UserRepository
from proxy.app.users.schemas import UserView
from proxy.app.users.service import UserAuthenticationError, UserService
from proxy.llm.adapter import LiteLLMResponsesAdapter
from proxy.model_deployments.repository import ModelDeploymentRepository
from proxy.model_deployments.service import ModelDeploymentService
from proxy.security.credentials import CredentialCipher


def get_session_factory(request: Request) -> async_sessionmaker:
    return request.app.state.session_factory


SessionFactoryDep = Annotated[async_sessionmaker, Depends(get_session_factory)]


def get_user_repository(session_factory: SessionFactoryDep) -> UserRepository:
    return UserRepository(session_factory)


UserRepositoryDep = Annotated[UserRepository, Depends(get_user_repository)]


def get_user_service(
    request: Request,
    repository: UserRepositoryDep,
) -> UserService:
    return UserService(repository, get_user_provider(request))


UserServiceDep = Annotated[UserService, Depends(get_user_service)]


async def get_current_user(
    request: Request,
    service: UserServiceDep,
) -> UserView:
    token = user_session_token(request)
    if token is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing bearer token.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    try:
        return await service.authenticate(token)
    except UserAuthenticationError as error:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(error),
            headers={"WWW-Authenticate": "Bearer"},
        ) from error


CurrentUserDep = Annotated[UserView, Depends(get_current_user)]


def get_model_deployment_repository(
    session_factory: SessionFactoryDep,
) -> ModelDeploymentRepository:
    return ModelDeploymentRepository(session_factory)


ModelDeploymentRepositoryDep = Annotated[
    ModelDeploymentRepository, Depends(get_model_deployment_repository)
]


def get_credential_cipher(request: Request) -> CredentialCipher:
    return request.app.state.credential_cipher


CredentialCipherDep = Annotated[CredentialCipher, Depends(get_credential_cipher)]


def get_model_deployment_service(
    repository: ModelDeploymentRepositoryDep,
    cipher: CredentialCipherDep,
) -> ModelDeploymentService:
    return ModelDeploymentService(repository, cipher)


ModelDeploymentServiceDep = Annotated[
    ModelDeploymentService, Depends(get_model_deployment_service)
]


def get_api_key_repository(session_factory: SessionFactoryDep) -> ApiKeyRepository:
    return ApiKeyRepository(session_factory)


ApiKeyRepositoryDep = Annotated[ApiKeyRepository, Depends(get_api_key_repository)]


def get_api_key_service(repository: ApiKeyRepositoryDep) -> ApiKeyService:
    return ApiKeyService(repository)


ApiKeyServiceDep = Annotated[ApiKeyService, Depends(get_api_key_service)]


def get_llm_adapter(request: Request) -> LiteLLMResponsesAdapter:
    return request.app.state.llm_adapter


LLMAdapterDep = Annotated[LiteLLMResponsesAdapter, Depends(get_llm_adapter)]


def get_model_usage_recorder(request: Request) -> ModelUsageRecorder:
    return request.app.state.model_usage_recorder


ModelUsageRecorderDep = Annotated[ModelUsageRecorder, Depends(get_model_usage_recorder)]


def get_model_usage_repository(
    session_factory: SessionFactoryDep,
) -> ModelUsageRepository:
    return ModelUsageRepository(session_factory)


ModelUsageRepositoryDep = Annotated[
    ModelUsageRepository, Depends(get_model_usage_repository)
]


def get_model_usage_service(
    repository: ModelUsageRepositoryDep,
) -> ModelUsageService:
    return ModelUsageService(repository)


ModelUsageServiceDep = Annotated[ModelUsageService, Depends(get_model_usage_service)]


def get_inference_service(
    models: ModelDeploymentServiceDep,
    adapter: LLMAdapterDep,
    usage: ModelUsageRecorderDep,
) -> InferenceService:
    return InferenceService(models, adapter, usage)


InferenceServiceDep = Annotated[InferenceService, Depends(get_inference_service)]
