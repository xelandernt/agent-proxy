from __future__ import annotations

import asyncio
import logging

from fastapi import FastAPI
from fastapi.routing import BaseRoute, Mount

from proxy.auth_providers.models import AuthProviderDefinition
from proxy.auth_providers.repository import (
    AuthProviderNotFound,
    AuthProvidersRepository,
)
from proxy.providers import ManagedAuthProviderConfig
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
        auth_provider_repository: AuthProvidersRepository,
        app_factory: McpServerAppFactory,
        gateway: FastAPI,
    ) -> None:
        self._lock = asyncio.Lock()
        self._repository = repository
        self._auth_provider_repository = auth_provider_repository
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
                await self._mount(config, await self._resolve_auth(config))

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
            app, mount_route = await self._prepare(
                config, await self._resolve_auth(config)
            )
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
            new_app, new_mount_route = await self._prepare(
                config, await self._resolve_auth(config)
            )
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

    async def create_auth_provider(
        self,
        definition: AuthProviderDefinition,
    ) -> AuthProviderDefinition:
        """Persist a reusable provider definition under the lifecycle lock."""

        async with self._lock:
            return await self._auth_provider_repository.create(definition)

    async def list_auth_providers(self) -> list[AuthProviderDefinition]:
        return await self._auth_provider_repository.list()

    async def update_auth_provider(
        self,
        name: str,
        auth: ManagedAuthProviderConfig,
    ) -> AuthProviderDefinition:
        """Replace a provider and atomically remount all linked live servers."""

        async with self._lock:
            if await self._auth_provider_repository.get(name) is None:
                raise AuthProviderNotFound(f"Unknown authentication provider '{name}'.")
            dependent_apps = sorted(
                (
                    app
                    for app in self._apps.values()
                    if app.config.auth_provider == name
                ),
                key=lambda app: app.name,
            )
            prepared: list[tuple[McpServerApp, Mount]] = []
            try:
                for app in dependent_apps:
                    prepared.append(await self._prepare(app.config, auth))
            except BaseException:
                await self._stop_prepared(prepared)
                raise
            try:
                updated = await self._auth_provider_repository.update(name, auth)
            except BaseException:
                await self._stop_prepared(prepared)
                raise

            old_apps: list[McpServerApp] = []
            for old_app, (new_app, mount_route) in zip(dependent_apps, prepared):
                old_apps.append(self._detach(old_app.name))
                self._attach(new_app, mount_route)
            for old_app in old_apps:
                try:
                    await old_app.stop()
                except Exception:
                    logger.exception(
                        "Failed to stop replaced MCP server '%s'", old_app.name
                    )
            return updated

    async def delete_auth_provider(self, name: str) -> None:
        """Delete an unused provider under the lifecycle lock."""

        async with self._lock:
            await self._auth_provider_repository.delete(name)

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

    async def _mount(
        self,
        config: McpServerConfig,
        auth: ManagedAuthProviderConfig | None,
    ) -> None:
        app, mount_route = await self._prepare(config, auth)
        self._attach(app, mount_route)

    async def _prepare(
        self,
        config: McpServerConfig,
        auth: ManagedAuthProviderConfig | None,
    ) -> tuple[McpServerApp, Mount]:
        app = self._factory.create(config, auth)
        mount_route = Mount(f"/{app.name}", app=app.get_mounted_app(), name=app.name)
        try:
            await app.start()
        except Exception:
            await app.stop()
            raise
        return app, mount_route

    async def _resolve_auth(
        self,
        config: McpServerConfig,
    ) -> ManagedAuthProviderConfig | None:
        if config.auth_provider is None:
            return None
        definition = await self._auth_provider_repository.get(config.auth_provider)
        if definition is None:
            raise AuthProviderNotFound(
                f"Unknown authentication provider '{config.auth_provider}'."
            )
        return definition.auth

    @staticmethod
    async def _stop_prepared(
        prepared: list[tuple[McpServerApp, Mount]],
    ) -> None:
        for app, _mount in prepared:
            try:
                await app.stop()
            except Exception:
                logger.exception("Failed to stop prepared MCP server '%s'", app.name)

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
