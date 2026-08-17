from __future__ import annotations

from typing import cast

import pytest
from fastapi import FastAPI

from proxy.auth_providers.models import AuthProviderDefinition
from proxy.auth_providers.repository import AuthProviderInUse
from proxy.providers import KeycloakAuthProviderConfig
from proxy.servers.app import McpServerAppFactory
from proxy.servers.manager import ServerManager
from proxy.servers.models import McpServerConfig
from proxy.servers.repository import ServersRepository


def provider(realm: str) -> AuthProviderDefinition:
    return AuthProviderDefinition(
        name="shared",
        auth=KeycloakAuthProviderConfig(
            provider="keycloak",
            realm_url=f"https://identity.example/realms/{realm}",
        ),
    )


def server(name: str, auth_provider: str | None = "shared") -> McpServerConfig:
    return McpServerConfig(
        name=name,
        upstream_url=f"https://upstream.example/{name}/mcp",
        auth_provider=auth_provider,
    )


class FakeApp:
    def __init__(self, config: McpServerConfig, call: int, fails: bool) -> None:
        self.config = config
        self.name = config.name
        self.call = call
        self.fails = fails
        self.stopped = False
        self.well_known_routes: list = []

    async def start(self) -> None:
        if self.fails:
            raise RuntimeError(f"startup failed on call {self.call}")

    async def stop(self) -> None:
        self.stopped = True

    def get_mounted_app(self) -> object:
        async def app(scope: object, receive: object, send: object) -> None:
            return None

        return app


class FakeFactory:
    def __init__(self) -> None:
        self.apps: list[FakeApp] = []
        self.fail_calls: set[int] = set()

    def create(self, config: McpServerConfig, _auth: object) -> FakeApp:
        call = len(self.apps)
        app = FakeApp(config, call, call in self.fail_calls)
        self.apps.append(app)
        return app


class FakeServersRepository:
    def __init__(self, configs: list[McpServerConfig]) -> None:
        self.configs = {config.name: config for config in configs}

    async def list(self) -> list[McpServerConfig]:
        return sorted(self.configs.values(), key=lambda config: config.name)


class FakeProvidersRepository:
    def __init__(self) -> None:
        self.definition = provider("old")
        self.fail_update = False

    async def get(self, name: str) -> AuthProviderDefinition | None:
        return self.definition if name == self.definition.name else None

    async def list(self) -> list[AuthProviderDefinition]:
        return [self.definition]

    async def update(self, name: str, auth: object) -> AuthProviderDefinition:
        if self.fail_update:
            raise RuntimeError("provider persistence failed")
        self.definition = AuthProviderDefinition(name=name, auth=auth)  # type: ignore[arg-type]
        return self.definition

    async def delete(self, name: str) -> None:
        raise AuthProviderInUse(name, ["zulu", "alpha"])


async def manager_fixture() -> tuple[
    ServerManager, FakeProvidersRepository, FakeFactory
]:
    servers = FakeServersRepository(
        [server("alpha"), server("beta"), server("public", None)]
    )
    providers = FakeProvidersRepository()
    factory = FakeFactory()
    manager = ServerManager(
        repository=cast(ServersRepository, servers),
        auth_provider_repository=cast(object, providers),
        app_factory=cast(McpServerAppFactory, factory),
        gateway=FastAPI(),
    )
    await manager.start()
    return manager, providers, factory


async def test_provider_update_cleans_every_candidate_on_start_failure() -> None:
    manager, providers, factory = await manager_fixture()
    previous = manager.snapshot()
    factory.fail_calls.add(4)

    with pytest.raises(RuntimeError, match="startup failed"):
        await manager.update_auth_provider("shared", provider("new").auth)

    assert manager.snapshot() == previous
    assert providers.definition == provider("old")
    assert factory.apps[3].stopped
    assert factory.apps[4].stopped
    assert not factory.apps[0].stopped
    assert not factory.apps[1].stopped
    await manager.stop()


async def test_provider_update_remounts_only_linked_servers() -> None:
    manager, providers, factory = await manager_fixture()

    updated = await manager.update_auth_provider("shared", provider("new").auth)

    assert updated.auth.realm_url.host == "identity.example"
    assert str(updated.auth.realm_url).endswith("/new")
    assert providers.definition == updated
    assert len(factory.apps) == 5
    assert factory.apps[0].stopped
    assert factory.apps[1].stopped
    assert not factory.apps[2].stopped
    assert not factory.apps[3].stopped
    assert not factory.apps[4].stopped
    await manager.stop()


async def test_provider_delete_is_blocked_by_dependents() -> None:
    manager, _providers, _factory = await manager_fixture()

    with pytest.raises(AuthProviderInUse, match="alpha, zulu"):
        await manager.delete_auth_provider("shared")
    await manager.stop()
