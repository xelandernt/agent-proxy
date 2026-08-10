from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import async_sessionmaker

from proxy.servers.models import (
    ServerConfig,
    McpServerConfig,
    config_to_auth_payload,
)


class ServerNotFound(KeyError):
    """Raised when a named server does not exist."""


class ServerNameTaken(ValueError):
    """Raised when creating a server whose name already exists."""


class ServersRepository:
    """Persistence for runtime MCP server configuration."""

    def __init__(
        self,
        session_factory: async_sessionmaker,
    ) -> None:
        self._session_factory = session_factory

    async def list(self) -> list[McpServerConfig]:
        stmt = select(ServerConfig).order_by(ServerConfig.name)
        async with self._session_factory() as session:
            rows = (await session.execute(stmt)).scalars().all()
        return [row.to_config() for row in rows]

    async def get(self, name: str) -> McpServerConfig | None:
        stmt = select(ServerConfig).where(ServerConfig.name == name)
        async with self._session_factory() as session:
            row = (await session.execute(stmt)).scalar_one_or_none()
        return row.to_config() if row is not None else None

    async def create(self, config: McpServerConfig) -> McpServerConfig:
        now = datetime.now(UTC)
        row = ServerConfig(
            name=config.name,
            description=config.description,
            upstream_url=str(config.upstream_url),
            verify_upstream_tls=config.verify_upstream_tls,
            auth=config_to_auth_payload(config),
            created_at=now,
            updated_at=now,
        )
        async with self._session_factory() as session:
            session.add(row)
            try:
                await session.commit()
            except IntegrityError as error:
                await session.rollback()
                raise ServerNameTaken(
                    f"MCP server name '{config.name}' already exists."
                ) from error
        return config

    async def update(
        self,
        name: str,
        config: McpServerConfig,
    ) -> McpServerConfig:
        stmt = select(ServerConfig).where(ServerConfig.name == name)
        async with self._session_factory() as session:
            row = (await session.execute(stmt)).scalar_one_or_none()
            if row is None:
                raise ServerNotFound(f"Unknown MCP server '{name}'.")
            row.description = config.description
            row.upstream_url = str(config.upstream_url)
            row.verify_upstream_tls = config.verify_upstream_tls
            row.auth = config_to_auth_payload(config)
            row.updated_at = datetime.now(UTC)
            await session.commit()
        return config

    async def delete(self, name: str) -> None:
        stmt = delete(ServerConfig).where(ServerConfig.name == name)
        async with self._session_factory() as session:
            result = await session.execute(stmt)
            if result.rowcount == 0:
                raise ServerNotFound(f"Unknown MCP server '{name}'.")
            await session.commit()
