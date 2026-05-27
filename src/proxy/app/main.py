from fastapi import FastAPI
import logfire
from loguru import logger
from starlette.middleware.cors import CORSMiddleware

from proxy.app.auth import build_auth_provider_registry
from proxy.app.mcp.endpoints import router as mcp_router
from proxy.app.mcp.sessions import SessionRegistry
from proxy.settings import CONFIG, Config

_OBSERVABILITY_CONFIGURED = False


def create_app(config: Config | None = None) -> FastAPI:
    settings = config or CONFIG

    app = FastAPI(title="Agent Proxy")
    app.state.config = settings
    app.state.auth_providers = build_auth_provider_registry(settings.mcp.groups)
    app.state.mcp_session_registry = SessionRegistry()
    app.state.upstream_asgi_app = None

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.middleware.cors.origins,
        allow_methods=settings.middleware.cors.allow_methods,
        allow_headers=settings.middleware.cors.allow_headers,
        allow_credentials=settings.middleware.cors.allow_credentials,
    )
    _configure_observability(app, settings)
    app.include_router(mcp_router)
    return app


def _configure_observability(app: FastAPI, settings: Config) -> None:
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
    logger.configure(handlers=[logfire.loguru_handler()])
    _OBSERVABILITY_CONFIGURED = True


app = create_app()
