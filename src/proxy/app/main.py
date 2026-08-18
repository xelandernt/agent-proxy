from __future__ import annotations

from collections.abc import AsyncGenerator
from contextlib import AsyncExitStack, asynccontextmanager
from typing import Any, cast

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from starlette.exceptions import HTTPException

from proxy.app.admin.auth import build_admin_provider
from proxy.app.admin.auth_providers import router as auth_providers_router
from proxy.app.admin.endpoints import (
    public_router as admin_public_router,
)
from proxy.app.admin.endpoints import router as admin_router
from proxy.app.admin.models import router as admin_models_router
from proxy.app.health import router as health_router
from proxy.app.inference.endpoints import router as inference_router
from proxy.app.inference.errors import (
    OpenAIErrorException,
    openai_error_handler,
    openai_http_error_handler,
    openai_unhandled_error_handler,
    openai_validation_handler,
)
from proxy.app.model_usage.admin_endpoints import router as admin_usage_router
from proxy.app.model_usage.endpoints import router as user_usage_router
from proxy.app.model_usage.recorder import ModelUsageRecorder
from proxy.app.usage.endpoints import router as usage_router
from proxy.app.usage.middleware import UsageRecorder
from proxy.app.users.account import router as user_account_router
from proxy.app.users.auth import build_user_provider
from proxy.app.users.endpoints import public_router as user_public_router
from proxy.app.users.endpoints import router as user_router
from proxy.app.well_known import router as well_known_router
from proxy.auth_providers.repository import AuthProvidersRepository
from proxy.database import create_all_tables, create_engine, create_session_factory
from proxy.llm.adapter import LiteLLMResponsesAdapter
from proxy.observability import configure_observability
from proxy.security.credentials import CredentialCipher
from proxy.servers.app import MCP_PROTOCOL_VERSION, McpServerAppFactory
from proxy.servers.manager import ServerManager
from proxy.servers.repository import ServersRepository
from proxy.settings import GatewayConfig, load_config


def create_app(config: GatewayConfig | None = None) -> FastAPI:
    """Create the multi-server MCP authentication gateway.

    Server definitions come from the database at runtime: the manager mounts
    and unmounts FastMCP apps live as servers are created, updated, and
    deleted.
    """

    settings = config or load_config()
    usage_engine = create_engine(settings.postgresql.connection_url)

    @asynccontextmanager
    async def lifespan(gateway: FastAPI) -> AsyncGenerator[None]:
        async with AsyncExitStack() as stack:
            await create_all_tables(usage_engine)
            session_factory = create_session_factory(usage_engine)
            gateway.state.session_factory = session_factory
            usage_recorder = UsageRecorder(session_factory)
            await usage_recorder.start()
            model_usage_recorder = ModelUsageRecorder(session_factory)
            await model_usage_recorder.start()
            gateway.state.model_usage_recorder = model_usage_recorder
            stack.push_async_callback(usage_engine.dispose)
            stack.push_async_callback(usage_recorder.stop)
            stack.push_async_callback(model_usage_recorder.stop)
            manager = ServerManager(
                repository=ServersRepository(session_factory),
                auth_provider_repository=AuthProvidersRepository(session_factory),
                app_factory=McpServerAppFactory(settings, usage_recorder),
                gateway=gateway,
            )
            await manager.start()
            gateway.state.server_manager = manager
            stack.push_async_callback(manager.stop)
            yield

    gateway = FastAPI(
        openapi_url=None,
        lifespan=lifespan,
    )
    cors = settings.middleware.cors
    gateway.add_middleware(
        CORSMiddleware,
        allow_origins=cors.origins,
        allow_credentials=cors.allow_credentials,
        allow_methods=cors.allow_methods,
        allow_headers=cors.allow_headers,
    )
    gateway.include_router(well_known_router)
    gateway.include_router(health_router)
    gateway.include_router(usage_router)
    gateway.include_router(admin_public_router)
    gateway.include_router(admin_router)
    gateway.include_router(auth_providers_router)
    gateway.include_router(admin_models_router)
    gateway.include_router(admin_usage_router)
    gateway.include_router(user_public_router)
    gateway.include_router(user_router)
    gateway.include_router(user_account_router)
    gateway.include_router(user_usage_router)
    gateway.include_router(inference_router)
    gateway.add_exception_handler(OpenAIErrorException, cast(Any, openai_error_handler))
    gateway.add_exception_handler(
        RequestValidationError, cast(Any, openai_validation_handler)
    )
    gateway.add_exception_handler(HTTPException, cast(Any, openai_http_error_handler))
    gateway.add_exception_handler(Exception, cast(Any, openai_unhandled_error_handler))

    admin_provider = build_admin_provider(
        settings.admin,
        str(settings.public_base_url),
    )
    gateway.state.admin_provider = admin_provider
    gateway.state.user_provider = build_user_provider(
        settings.user,
        str(settings.public_base_url),
    )
    gateway.state.credential_cipher = CredentialCipher(
        settings.model_gateway.credential_encryption_key
    )
    gateway.state.llm_adapter = LiteLLMResponsesAdapter()

    gateway.state.config = settings
    gateway.state.usage_engine = usage_engine
    configure_observability(gateway, settings.logfire)
    return gateway


__all__ = ["MCP_PROTOCOL_VERSION", "create_app"]
