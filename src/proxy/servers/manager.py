from __future__ import annotations

import asyncio

from fastapi import FastAPI
from fastapi.routing import BaseRoute, Mount

from proxy.servers.app import McpServerApp, McpServerAppFactory
from proxy.servers.models import McpServerConfig
from proxy.servers.repository import ServerNotFound, ServersRepository


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
            await self._repository.create(config)
            try:
                await self._mount(config)
            except Exception:
                await self._repository.delete(config.name)
                raise
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
            new_app = self._factory.create(config)
            try:
                await self._repository.update(name, config)
            except Exception:
                await new_app.stop()
                raise
            await self._unmount(name)
            await self._mount_app(new_app)
            return config

    async def delete(self, name: str) -> None:
        """Unmount and delete a server, or raise ServerNotFound."""

        async with self._lock:
            if name not in self._apps:
                raise ServerNotFound(f"Unknown MCP server '{name}'.")
            await self._unmount(name)
            await self._repository.delete(name)

    async def _mount(self, config: McpServerConfig) -> None:
        app = self._factory.create(config)
        try:
            await self._mount_app(app)
        except Exception:
            await app.stop()
            raise

    async def _mount_app(self, app: McpServerApp) -> None:
        await app.start()
        try:
            self._gateway.router.routes.extend(app.well_known_routes)
            mount_route = Mount(
                f"/{app.name}", app=app.get_mounted_app(), name=app.name
            )
            self._gateway.router.routes.append(mount_route)
        except Exception:
            await app.stop()
            raise
        self._apps[app.name] = app
        self._mount_routes[app.name] = mount_route

    async def _unmount(self, name: str) -> None:
        app = self._apps.pop(name)
        mount_route = self._mount_routes.pop(name)
        self._remove_route(mount_route)
        for route in app.well_known_routes:
            self._remove_route(route)
        await app.stop()

    def _remove_route(self, route: BaseRoute) -> None:
        self._gateway.router.routes[:] = [
            existing
            for existing in self._gateway.router.routes
            if existing is not route
        ]

    def __len__(self) -> int:
        return len(self._apps)
