from __future__ import annotations

from collections.abc import AsyncGenerator
from contextlib import AsyncExitStack, asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from sqlalchemy import inspect, text

from proxy.app.admin.auth import build_admin_provider
from proxy.app.admin.endpoints import (
    public_router as admin_public_router,
)
from proxy.app.admin.endpoints import router as admin_router
from proxy.app.usage.endpoints import router as usage_router
from proxy.app.usage.middleware import UsageRecorder
from proxy.app.well_known import router as well_known_router
from proxy.database import Base, create_engine, create_session_factory
from proxy.observability import configure_observability
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
    usage_engine = create_engine(settings.database.url)

    @asynccontextmanager
    async def lifespan(gateway: FastAPI) -> AsyncGenerator[None]:
        async with AsyncExitStack() as stack:
            async with usage_engine.begin() as connection:
                await connection.run_sync(Base.metadata.create_all)

                def _ensure_forwarding_column(sync_connection) -> None:
                    columns = {
                        column["name"]
                        for column in inspect(sync_connection).get_columns("servers")
                    }
                    if "forward_client_credentials" not in columns:
                        sync_connection.execute(
                            text(
                                "ALTER TABLE servers ADD COLUMN "
                                "forward_client_credentials BOOLEAN NOT NULL "
                                "DEFAULT FALSE"
                            )
                        )

                await connection.run_sync(_ensure_forwarding_column)
            session_factory = create_session_factory(usage_engine)
            usage_recorder = UsageRecorder(session_factory)
            await usage_recorder.start()
            stack.push_async_callback(usage_engine.dispose)
            stack.push_async_callback(usage_recorder.stop)
            manager = ServerManager(
                repository=ServersRepository(session_factory),
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
    cors_origins = [str(origin).rstrip("/") for origin in settings.cors_origins]
    if cors_origins:
        gateway.add_middleware(
            CORSMiddleware,
            allow_origins=cors_origins,
            allow_credentials=True,
            allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
            allow_headers=["*"],
        )
    gateway.include_router(well_known_router)
    gateway.include_router(usage_router)
    gateway.include_router(admin_public_router)
    gateway.include_router(admin_router)

    admin_provider = build_admin_provider(
        settings.admin,
        str(settings.public_base_url),
    )
    gateway.state.admin_provider = admin_provider

    gateway.state.config = settings
    gateway.state.usage_engine = usage_engine
    configure_observability(gateway, settings.logfire)
    return gateway


__all__ = ["MCP_PROTOCOL_VERSION", "create_app"]
