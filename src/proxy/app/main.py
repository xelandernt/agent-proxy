from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import AsyncExitStack, asynccontextmanager
from typing import Final

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.routing import BaseRoute
from fastmcp.server import create_proxy
from fastmcp.server.http import StarletteWithLifespan as FastMCPApplication

from proxy.app.well_known import router as well_known_router
from proxy.observability import configure_observability
from proxy.providers import load_auth_provider
from proxy.settings import GatewayConfig, McpServerConfig, load_config
from proxy.transport import create_upstream_transport

MCP_PROTOCOL_VERSION: Final = "2026-07-28"


def _create_mcp_app(
    config: GatewayConfig,
    server: McpServerConfig,
) -> FastMCPApplication:
    """Build one isolated FastMCP auth proxy application."""

    auth = load_auth_provider(
        server.auth,
        base_url=config.server_base_url(server),
    )
    transport = create_upstream_transport(
        str(server.upstream_url),
        verify_tls=server.verify_upstream_tls,
    )
    proxy = create_proxy(
        transport,
        mode=MCP_PROTOCOL_VERSION,
        name=server.name,
        auth=auth,
        provider_error_strategy="raise",
    )
    return proxy.http_app(path="/mcp", stateless_http=True)


def _take_well_known_routes(app: FastMCPApplication) -> list[BaseRoute]:
    """Move FastMCP's standards-defined discovery routes to the gateway root."""

    well_known_routes = [
        route
        for route in app.routes
        if getattr(route, "path", "").startswith("/.well-known/")
    ]
    app.routes[:] = [route for route in app.routes if route not in well_known_routes]
    return well_known_routes


def create_app(config: GatewayConfig | None = None) -> FastAPI:
    """Create the multi-server MCP authentication gateway."""

    settings = config or load_config()
    mcp_apps = {
        server.name: _create_mcp_app(settings, server) for server in settings.servers
    }

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        async with AsyncExitStack() as stack:
            for mcp_app in mcp_apps.values():
                await stack.enter_async_context(mcp_app.lifespan(mcp_app))
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
            allow_methods=["GET"],
            allow_headers=["*"],
        )
    gateway.include_router(well_known_router)
    for name, mcp_app in mcp_apps.items():
        gateway.router.routes.extend(_take_well_known_routes(mcp_app))
        gateway.mount(f"/{name}", mcp_app, name=name)

    gateway.state.config = settings
    gateway.state.server_apps = mcp_apps
    configure_observability(gateway, settings.logfire)
    return gateway
