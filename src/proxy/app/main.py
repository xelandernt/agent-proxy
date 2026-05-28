from contextlib import asynccontextmanager
import sys
from typing import Any

from fastapi import FastAPI
import logfire
from loguru import logger
from starlette.middleware.cors import CORSMiddleware

from proxy.app.mcp.dependencies import get_config
from proxy.app.mcp.endpoints import router as mcp_router
from proxy.app.mcp.sessions import shutdown_session_registry, startup_session_registry
from proxy.settings import CONFIG, Config

_OBSERVABILITY_CONFIGURED = False


def create_app(config: Config | None = None) -> FastAPI:
    settings = config or CONFIG

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        await startup_session_registry(settings.session_registry)
        try:
            yield
        finally:
            await shutdown_session_registry(settings.session_registry)

    app = FastAPI(title="Agent Proxy", lifespan=lifespan)
    if config is not None:
        app.dependency_overrides[get_config] = lambda: config

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.middleware.cors.origins,
        allow_methods=settings.middleware.cors.allow_methods,
        allow_headers=settings.middleware.cors.allow_headers,
        allow_credentials=settings.middleware.cors.allow_credentials,
    )
    configure_observability(app, settings)
    app.include_router(mcp_router)
    return app


def configure_observability(app: FastAPI, settings: Config) -> None:
    global _OBSERVABILITY_CONFIGURED
    if _OBSERVABILITY_CONFIGURED:
        return

    logfire.configure(
        send_to_logfire="if-token-present",
        environment=settings.logfire.environment,
        service_name=settings.logfire.service_name,
        token=settings.logfire.token.get_secret_value()
        if settings.logfire.token
        else None,
    )
    logfire.instrument_fastapi(app)
    logfire.instrument_system_metrics(base="basic")
    handlers: list[Any] = []
    if settings.logfire.environment == "dev":
        handlers.append(
            {
                "sink": sys.stderr,
                "level": "DEBUG",
                "format": "{time:YYYY-MM-DD HH:mm:ss.SSS} | {level} | {message}",
            }
        )
    handlers.append(logfire.loguru_handler())
    logger.configure(handlers=handlers)
    _OBSERVABILITY_CONFIGURED = True


app = create_app()
