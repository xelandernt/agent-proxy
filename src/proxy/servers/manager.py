from __future__ import annotations

import asyncio
import logging

from fastapi import FastAPI
from fastapi.routing import BaseRoute, Mount

from proxy.servers.app import McpServerApp, McpServerAppFactory
from proxy.servers.models import McpServerConfig
from proxy.servers.repository import ServerNameTaken, ServerNotFound, ServersRepository

logger = logging.getLogger(__name__)


class ServerManager:
    """Runtime authority over the gateway's mounted MCP servers.

    Every mutation is serialized on an internal lock and applies to both the
    database and the live gateway, so changes take effect without a restart.
    """

    def __init__(
        self,
        *,
        repository: ServersRepository,
        app_factory: McpServerAppFactory,
        gateway: FastAPI,
    ) -> None:
        self._lock = asyncio.Lock()
        self._repository = repository
        self._factory = app_factory
        self._gateway = gateway
        self._apps: dict[str, McpServerApp] = {}
        self._mount_routes: dict[str, BaseRoute] = {}

    def snapshot(self) -> list[McpServerConfig]:
        """Return the current runtime server configs in name order."""

        return [app.config for app in sorted(self._apps.values(), key=lambda a: a.name)]

    def get(self, name: str) -> McpServerConfig | None:
        app = self._apps.get(name)
        return app.config if app is not None else None

    async def start(self) -> None:
        """Load every persisted server and mount it on the gateway."""

        async with self._lock:
            for config in await self._repository.list():
                await self._mount(config)

    async def stop(self) -> None:
        """Tear down every mounted server app."""

        async with self._lock:
            for name in list(self._apps):
                await self._unmount(name)

    async def create(self, config: McpServerConfig) -> McpServerConfig:
        """Persist and live-mount a new server, or raise ServerNameTaken."""

        async with self._lock:
            if config.name in self._apps:
                raise ServerNameTaken(
                    f"MCP server name '{config.name}' already exists."
                )
            app, mount_route = await self._prepare(config)
            try:
                await self._repository.create(config)
            except Exception:
                await app.stop()
                raise
            self._attach(app, mount_route)
            return config

    async def update(
        self,
        name: str,
        config: McpServerConfig,
    ) -> McpServerConfig:
        """Replace a server's definition live, or raise ServerNotFound."""

        async with self._lock:
            if name not in self._apps:
                raise ServerNotFound(f"Unknown MCP server '{name}'.")
            if config.name != name:
                raise ValueError("MCP server names are immutable.")
            new_app, new_mount_route = await self._prepare(config)
            try:
                await self._repository.update(name, config)
            except Exception:
                await new_app.stop()
                raise
            old_app = self._detach(name)
            self._attach(new_app, new_mount_route)
            try:
                await old_app.stop()
            except Exception:
                logger.exception("Failed to stop replaced MCP server '%s'", name)
            return config

    async def delete(self, name: str) -> None:
        """Unmount and delete a server, or raise ServerNotFound."""

        async with self._lock:
            if name not in self._apps:
                raise ServerNotFound(f"Unknown MCP server '{name}'.")
            await self._repository.delete(name)
            app = self._detach(name)
            try:
                await app.stop()
            except Exception:
                logger.exception("Failed to stop deleted MCP server '%s'", name)

    async def _mount(self, config: McpServerConfig) -> None:
        app, mount_route = await self._prepare(config)
        self._attach(app, mount_route)

    async def _prepare(self, config: McpServerConfig) -> tuple[McpServerApp, Mount]:
        app = self._factory.create(config)
        mount_route = Mount(f"/{app.name}", app=app.get_mounted_app(), name=app.name)
        try:
            await app.start()
        except Exception:
            await app.stop()
            raise
        return app, mount_route

    def _attach(self, app: McpServerApp, mount_route: Mount) -> None:
        self._gateway.router.routes.extend((*app.well_known_routes, mount_route))
        self._apps[app.name] = app
        self._mount_routes[app.name] = mount_route

    async def _unmount(self, name: str) -> None:
        app = self._detach(name)
        await app.stop()

    def _detach(self, name: str) -> McpServerApp:
        app = self._apps.pop(name)
        mount_route = self._mount_routes.pop(name)
        self._remove_route(mount_route)
        for route in app.well_known_routes:
            self._remove_route(route)
        return app

    def _remove_route(self, route: BaseRoute) -> None:
        self._gateway.router.routes[:] = [
            existing
            for existing in self._gateway.router.routes
            if existing is not route
        ]

    def __len__(self) -> int:
        return len(self._apps)
