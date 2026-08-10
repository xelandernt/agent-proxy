from __future__ import annotations

from sqlalchemy import text

from proxy.database import Base, create_engine, create_session_factory
from proxy.servers.models import McpServerConfig
from proxy.servers.repository import ServersRepository


def seed_servers(database_url: str, servers: list[McpServerConfig]) -> None:
    """Reset and repopulate the servers table (for sync test code)."""

    import asyncio

    asyncio.run(seed_servers_async(database_url, servers))


async def seed_servers_async(
    database_url: str,
    servers: list[McpServerConfig],
) -> None:
    """Reset and repopulate the servers table (for async test code)."""

    engine = create_engine(database_url)
    try:
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
            await connection.execute(text("DELETE FROM servers"))
        repository = ServersRepository(create_session_factory(engine))
        for server in servers:
            await repository.create(server)
    finally:
        await engine.dispose()
