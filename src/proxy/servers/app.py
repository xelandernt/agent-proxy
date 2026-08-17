from __future__ import annotations

import asyncio

from fastapi.routing import BaseRoute
from fastmcp.server import create_proxy
from fastmcp.server.http import StarletteWithLifespan as FastMCPApplication
from starlette.types import ASGIApp

from proxy.app.usage.middleware import UsageRecorder, apply_usage_tracing
from proxy.providers import ManagedAuthProviderConfig, load_auth_provider
from proxy.servers.models import McpServerConfig, server_base_url
from proxy.settings import GatewayConfig
from proxy.transport import create_upstream_transport

MCP_PROTOCOL_VERSION = "2026-07-28"


class McpServerApp:
    """One mounted FastMCP auth proxy app with precise teardown bookkeeping.

    The FastMCP lifespan is driven by an ``anyio`` task group that must be
    entered and exited from a single task, so this unit owns a dedicated task
    for the app's entire lifetime. Requests arrive on other tasks; only
    ``start`` and ``stop`` touch the lifespan.
    """

    def __init__(
        self,
        *,
        config: McpServerConfig,
        mcp_app: FastMCPApplication,
        well_known_routes: list[BaseRoute],
        traced_app: ASGIApp,
    ) -> None:
        self.config = config
        self.mcp_app = mcp_app
        self.well_known_routes = well_known_routes
        self._traced_app = traced_app
        self._lifespan_task: asyncio.Task[None] | None = None
        self._started = asyncio.Event()
        self._stopping = asyncio.Event()
        self._failure: BaseException | None = None

    @property
    def name(self) -> str:
        return self.config.name

    async def start(self) -> None:
        """Start the lifespan owner task and wait until the app is serving."""

        if self._lifespan_task is not None:
            return
        self._lifespan_task = asyncio.create_task(self._run_lifespan())
        await self._started.wait()
        if self._failure is not None:
            self._failure = None
            task, self._lifespan_task = self._lifespan_task, None
            await task

    async def _run_lifespan(self) -> None:
        try:
            async with self.mcp_app.lifespan(self.mcp_app):
                self._started.set()
                await self._stopping.wait()
        except BaseException as error:
            self._failure = error
            self._started.set()
            raise

    async def stop(self) -> None:
        """Signal the lifespan owner task and wait for full teardown."""

        if self._lifespan_task is None:
            return
        task = self._lifespan_task
        self._stopping.set()
        try:
            await task
        finally:
            self._lifespan_task = None

    def get_mounted_app(self) -> ASGIApp:
        """Return the ASGI app to mount under ``/{name}``."""

        return self._traced_app


class McpServerAppFactory:
    """Builds isolated FastMCP auth proxy applications from server configs."""

    def __init__(
        self,
        config: GatewayConfig,
        usage_recorder: UsageRecorder | None,
    ) -> None:
        self._config = config
        self._usage_recorder = usage_recorder

    def create(
        self,
        server: McpServerConfig,
        auth: ManagedAuthProviderConfig | None,
    ) -> McpServerApp:
        """Build one app, hoisting its well-known routes out for gateway mounting."""

        base_url = server_base_url(str(self._config.public_base_url), server.name)
        loaded_auth = (
            load_auth_provider(auth, base_url=base_url) if auth is not None else None
        )
        transport = create_upstream_transport(
            str(server.upstream_url),
            verify_tls=server.verify_upstream_tls,
            forward_client_credentials=server.forward_client_credentials,
        )
        proxy = create_proxy(
            transport,
            mode=MCP_PROTOCOL_VERSION,
            name=server.name,
            auth=loaded_auth,
            provider_error_strategy="raise",
        )
        mcp_app = proxy.http_app(path="/mcp", stateless_http=True)
        well_known_routes = _take_well_known_routes(mcp_app)
        traced_app = apply_usage_tracing(
            mcp_app,
            server_name=server.name,
            recorder=self._usage_recorder,
        )
        return McpServerApp(
            config=server,
            mcp_app=mcp_app,
            well_known_routes=well_known_routes,
            traced_app=traced_app,
        )


def _take_well_known_routes(app: FastMCPApplication) -> list[BaseRoute]:
    """Move FastMCP's standards-defined discovery routes to the gateway root."""

    well_known_routes = [
        route
        for route in app.routes
        if getattr(route, "path", "").startswith("/.well-known/")
    ]
    app.routes[:] = [route for route in app.routes if route not in well_known_routes]
    return well_known_routes
