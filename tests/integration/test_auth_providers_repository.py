from __future__ import annotations

from collections.abc import AsyncIterator

import pytest
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker

from proxy.auth_providers.models import AuthProviderDefinition
from proxy.auth_providers.repository import (
    AuthProviderInUse,
    AuthProviderNameTaken,
    AuthProviderNotFound,
    AuthProvidersRepository,
)
from proxy.database import Base, create_engine, create_session_factory
from proxy.providers import Auth0AuthProviderConfig, KeycloakAuthProviderConfig
from proxy.servers.models import McpServerConfig
from proxy.servers.repository import ServersRepository


@pytest.fixture()
async def session_factory(
    postgresql_url: str,
) -> AsyncIterator[async_sessionmaker]:
    engine: AsyncEngine = create_engine(postgresql_url)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    try:
        yield create_session_factory(engine)
    finally:
        await engine.dispose()


def keycloak(name: str = "main") -> AuthProviderDefinition:
    return AuthProviderDefinition(
        name=name,
        auth=KeycloakAuthProviderConfig(
            provider="keycloak",
            realm_url="https://identity.example/realms/test",
        ),
    )


async def test_provider_crud_is_sorted_and_typed(
    session_factory: async_sessionmaker,
) -> None:
    repository = AuthProvidersRepository(session_factory)
    await repository.create(keycloak("zulu"))
    await repository.create(keycloak("alpha"))

    assert [item.name for item in await repository.list()] == ["alpha", "zulu"]
    assert await repository.get("alpha") == keycloak("alpha")

    updated = await repository.update(
        "alpha",
        Auth0AuthProviderConfig(
            provider="auth0",
            config_url="https://tenant.example/.well-known/openid-configuration",
            client_id="client",
            client_secret="secret",
            audience="https://api.example",
        ),
    )
    assert updated.auth.provider == "auth0"


async def test_provider_duplicate_unknown_and_corrupt_cases(
    session_factory: async_sessionmaker,
) -> None:
    repository = AuthProvidersRepository(session_factory)
    await repository.create(keycloak())
    with pytest.raises(AuthProviderNameTaken):
        await repository.create(keycloak())
    with pytest.raises(AuthProviderNotFound):
        await repository.update("missing", keycloak().auth)
    with pytest.raises(AuthProviderNotFound):
        await repository.delete("missing")

    from sqlalchemy import text

    async with session_factory() as session:
        await session.execute(
            text(
                "INSERT INTO auth_providers (name, auth, created_at, updated_at) "
                "VALUES ('corrupt', :auth, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"
            ),
            {"auth": '{"provider": "keycloak"}'},
        )
        await session.commit()
    with pytest.raises(ValidationError):
        await repository.get("corrupt")


async def test_in_use_provider_delete_lists_sorted_dependents(
    session_factory: async_sessionmaker,
) -> None:
    await AuthProvidersRepository(session_factory).create(keycloak())
    servers = ServersRepository(session_factory)
    for name in ("zulu", "alpha"):
        await servers.create(
            McpServerConfig(
                name=name,
                upstream_url="https://upstream.example/mcp",
                auth_provider="main",
            )
        )

    with pytest.raises(AuthProviderInUse) as error:
        await AuthProvidersRepository(session_factory).delete("main")
    assert error.value.dependent_servers == ("alpha", "zulu")
