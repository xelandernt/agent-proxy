from __future__ import annotations

from sqlalchemy import text

from proxy.auth_providers.models import AuthProviderDefinition
from proxy.auth_providers.repository import AuthProvidersRepository
from proxy.database import Base, create_engine, create_session_factory
from proxy.providers import KeycloakAuthProviderConfig
from proxy.servers.models import McpServerConfig
from proxy.servers.repository import ServersRepository


def seed_servers(
    database_url: str,
    servers: list[McpServerConfig],
    providers: list[AuthProviderDefinition] | None = None,
) -> None:
    """Reset and repopulate provider and server tables (sync wrapper)."""

    import asyncio

    asyncio.run(seed_servers_async(database_url, servers, providers))


async def seed_servers_async(
    database_url: str,
    servers: list[McpServerConfig],
    providers: list[AuthProviderDefinition] | None = None,
) -> None:
    """Reset and repopulate provider and server tables."""

    engine = create_engine(database_url)
    try:
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
            await connection.execute(text("DELETE FROM servers"))
            await connection.execute(text("DELETE FROM auth_providers"))
        provider_repository = AuthProvidersRepository(create_session_factory(engine))
        definitions = (
            providers
            if providers is not None
            else [
                AuthProviderDefinition(
                    name=provider_name,
                    auth=KeycloakAuthProviderConfig(
                        provider="keycloak",
                        realm_url="https://identity.example/realms/test",
                    ),
                )
                for provider_name in sorted(
                    {
                        server.auth_provider
                        for server in servers
                        if server.auth_provider is not None
                    }
                )
            ]
        )
        for provider in definitions:
            await provider_repository.create(provider)
        repository = ServersRepository(create_session_factory(engine))
        for server in servers:
            await repository.create(server)
    finally:
        await engine.dispose()
