from __future__ import annotations

from typing import cast

import pytest
from fastapi import FastAPI

from proxy.servers.app import McpServerAppFactory
from proxy.servers.manager import ServerManager
from proxy.servers.models import McpServerConfig
from proxy.servers.repository import ServersRepository


def server(upstream_url: str = "http://127.0.0.1:9/mcp") -> McpServerConfig:
    return McpServerConfig.model_validate(
        {
            "name": "calendar",
            "upstream_url": upstream_url,
            "auth": {
                "provider": "keycloak",
                "realm_url": "https://identity.example/realms/test",
            },
        }
    )


class FakeApp:
    def __init__(self, config: McpServerConfig, *, start_fails: bool = False) -> None:
        self.config = config
        self.name = config.name
        self.well_known_routes: list = []
        self.start_fails = start_fails
        self.stopped = False

    async def start(self) -> None:
        if self.start_fails:
            raise RuntimeError("startup failed")

    async def stop(self) -> None:
        self.stopped = True

    def get_mounted_app(self) -> object:
        async def app(scope: object, receive: object, send: object) -> None:
            return None

        return app


class FakeFactory:
    def __init__(self) -> None:
        self.created: list[FakeApp] = []
        self.fail_next_start = False

    def create(self, config: McpServerConfig) -> FakeApp:
        app = FakeApp(config, start_fails=self.fail_next_start)
        self.fail_next_start = False
        self.created.append(app)
        return app


class FakeRepository:
    def __init__(self, config: McpServerConfig) -> None:
        self.config: McpServerConfig | None = config
        self.fail_update = False
        self.fail_delete = False

    async def list(self) -> list[McpServerConfig]:
        return [self.config] if self.config is not None else []

    async def update(self, name: str, config: McpServerConfig) -> McpServerConfig:
        if self.fail_update:
            raise RuntimeError("database update failed")
        self.config = config
        return config

    async def delete(self, name: str) -> None:
        if self.fail_delete:
            raise RuntimeError("database delete failed")
        self.config = None


async def manager_fixture() -> tuple[ServerManager, FakeRepository, FakeFactory]:
    repository = FakeRepository(server())
    factory = FakeFactory()
    manager = ServerManager(
        repository=cast(ServersRepository, repository),
        app_factory=cast(McpServerAppFactory, factory),
        gateway=FastAPI(),
    )
    await manager.start()
    return manager, repository, factory


async def test_update_start_failure_leaves_current_state_untouched() -> None:
    manager, repository, factory = await manager_fixture()
    previous = manager.get("calendar")
    factory.fail_next_start = True

    with pytest.raises(RuntimeError, match="startup failed"):
        await manager.update("calendar", server("http://127.0.0.1:99/mcp"))

    assert manager.get("calendar") == previous
    assert repository.config == previous
    await manager.stop()


async def test_update_persistence_failure_stops_replacement() -> None:
    manager, repository, factory = await manager_fixture()
    previous = manager.get("calendar")
    repository.fail_update = True

    with pytest.raises(RuntimeError, match="database update failed"):
        await manager.update("calendar", server("http://127.0.0.1:99/mcp"))

    assert manager.get("calendar") == previous
    assert repository.config == previous
    assert factory.created[-1].stopped
    await manager.stop()


async def test_delete_persistence_failure_leaves_current_state_mounted() -> None:
    manager, repository, _factory = await manager_fixture()
    previous = manager.get("calendar")
    repository.fail_delete = True

    with pytest.raises(RuntimeError, match="database delete failed"):
        await manager.delete("calendar")

    assert manager.get("calendar") == previous
    assert repository.config == previous
    await manager.stop()
