from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import AbstractAsyncContextManager, AsyncExitStack, asynccontextmanager
from typing import Final, Protocol, cast

from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.routing import ASGIApp, BaseRoute
from fastmcp.server import create_proxy
from scalar_fastapi import AgentScalarConfig, get_scalar_api_reference

from proxy.app.openapi import (
    MCP_PROTOCOL_VERSION,
    OpenApiDocument,
    create_openapi_document,
)
from proxy.observability import configure_observability
from proxy.providers import load_auth_provider
from proxy.settings import GatewayConfig, McpServerConfig, load_config
from proxy.transport import create_upstream_transport

SCALAR_JAVASCRIPT_URL: Final = (
    "https://cdn.jsdelivr.net/npm/@scalar/api-reference@1.64.0"
)


class FastMcpRouter(Protocol):
    """Lifespan surface used from FastMCP's internal HTTP application."""

    def lifespan_context(
        self,
        app: FastMcpApplication,
    ) -> AbstractAsyncContextManager[object]: ...


class FastMcpApplication(Protocol):
    """ASGI application features required by the FastAPI gateway."""

    routes: list[BaseRoute]
    router: FastMcpRouter


def create_server_app(
    config: GatewayConfig,
    server: McpServerConfig,
) -> FastMcpApplication:
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
    return cast(
        FastMcpApplication,
        proxy.http_app(path="/mcp", stateless_http=True),
    )


def create_app(config: GatewayConfig | None = None) -> FastAPI:
    """Create the multi-server MCP authentication gateway."""

    settings = config or load_config()
    child_apps = {
        server.name: create_server_app(settings, server) for server in settings.servers
    }
    well_known_routes: list[BaseRoute] = []
    for child_app in child_apps.values():
        child_well_known_routes = [
            route
            for route in child_app.routes
            if getattr(route, "path", "").startswith("/.well-known/")
        ]
        well_known_routes.extend(child_well_known_routes)
        child_app.routes[:] = [
            route for route in child_app.routes if route not in child_well_known_routes
        ]

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        async with AsyncExitStack() as stack:
            for child_app in child_apps.values():
                await stack.enter_async_context(
                    child_app.router.lifespan_context(child_app)
                )
            yield

    gateway = FastAPI(
        title="agent-proxy",
        summary="Authenticated access to modern MCP servers.",
        description=(
            f"Authentication gateway for MCP {MCP_PROTOCOL_VERSION}. MCP tools, "
            "resources, and prompts are discovered through the protocol at runtime."
        ),
        redoc_url=None,
        lifespan=lifespan,
    )

    async def scalar_reference() -> HTMLResponse:
        return get_scalar_api_reference(
            openapi_url=gateway.openapi_url,
            title="agent-proxy API reference",
            scalar_js_url=SCALAR_JAVASCRIPT_URL,
            telemetry=False,
            agent=AgentScalarConfig(disabled=True),
        )

    gateway.add_api_route(
        "/scalar",
        scalar_reference,
        methods=["GET"],
        include_in_schema=False,
        name="scalar",
    )
    gateway.router.routes.extend(well_known_routes)
    for name, child_app in child_apps.items():
        gateway.mount(f"/{name}", cast(ASGIApp, child_app), name=name)

    openapi_document = create_openapi_document(settings)

    def openapi() -> OpenApiDocument:
        return openapi_document

    gateway.openapi = openapi
    gateway.state.config = settings
    gateway.state.server_apps = child_apps
    configure_observability(gateway, settings.logfire)
    return gateway
