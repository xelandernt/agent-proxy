from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status
import logfire
from loguru import logger
from starlette.responses import JSONResponse
from starlette.middleware.cors import CORSMiddleware

from proxy.app.mcp.endpoints import router as mcp_router
from proxy.app.mcp.service import UpstreamConnectionError
from proxy.app.runtime import build_app_runtime
from proxy.sessions.types import SessionOwnershipConflictError
from proxy.settings import CONFIG, ProxyConfig

_OBSERVABILITY_CONFIGURED = False


def create_app(config: ProxyConfig | None = None) -> FastAPI:
    settings = config or CONFIG
    runtime = build_app_runtime(settings)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        app.state.runtime = runtime
        await runtime.session_database.startup()
        try:
            yield
        finally:
            await runtime.session_database.shutdown()

    app = FastAPI(title="Agent Proxy", lifespan=lifespan)
    app.state.runtime = runtime

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.middleware.cors.origins,
        allow_methods=settings.middleware.cors.allow_methods,
        allow_headers=settings.middleware.cors.allow_headers,
        allow_credentials=settings.middleware.cors.allow_credentials,
    )
    configure_observability(app, settings)
    add_exception_handlers(app)
    app.include_router(mcp_router)
    return app


def add_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(UpstreamConnectionError)
    async def upstream_connection_error_handler(
        _: Request, exc: UpstreamConnectionError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_502_BAD_GATEWAY,
            content={"detail": str(exc)},
        )

    @app.exception_handler(SessionOwnershipConflictError)
    async def session_ownership_conflict_handler(
        _: Request, __: SessionOwnershipConflictError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_409_CONFLICT,
            content={
                "detail": "Protected session is already bound to another principal."
            },
        )


def configure_observability(app: FastAPI, settings: ProxyConfig) -> None:
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
