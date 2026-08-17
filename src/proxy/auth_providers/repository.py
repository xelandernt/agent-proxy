from __future__ import annotations

import builtins
from datetime import UTC, datetime

from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import async_sessionmaker

from proxy.auth_providers.models import (
    AuthProviderDefinition,
    config_to_auth_payload,
)
from proxy.auth_providers.persistence import AuthProviderRecord
from proxy.providers import ManagedAuthProviderConfig
from proxy.servers.models import ServerConfig


class AuthProviderNotFound(KeyError):
    """Raised when a named managed provider does not exist."""


class AuthProviderNameTaken(ValueError):
    """Raised when creating a duplicate managed provider name."""


class AuthProviderInUse(ValueError):
    """Raised when deleting a provider linked from one or more servers."""

    def __init__(self, name: str, dependent_servers: list[str]) -> None:
        self.name = name
        self.dependent_servers = tuple(sorted(dependent_servers))
        joined = ", ".join(self.dependent_servers)
        super().__init__(
            f"Authentication provider '{name}' is used by servers: {joined}."
        )


class AuthProvidersRepository:
    """Persistence for reusable managed authentication providers."""

    def __init__(self, session_factory: async_sessionmaker) -> None:
        self._session_factory = session_factory

    async def list(self) -> list[AuthProviderDefinition]:
        stmt = select(AuthProviderRecord).order_by(AuthProviderRecord.name)
        async with self._session_factory() as session:
            rows = (await session.execute(stmt)).scalars().all()
        return [self._to_definition(row) for row in rows]

    async def get(self, name: str) -> AuthProviderDefinition | None:
        stmt = select(AuthProviderRecord).where(AuthProviderRecord.name == name)
        async with self._session_factory() as session:
            row = (await session.execute(stmt)).scalar_one_or_none()
        return self._to_definition(row) if row is not None else None

    async def create(
        self, definition: AuthProviderDefinition
    ) -> AuthProviderDefinition:
        now = datetime.now(UTC)
        row = AuthProviderRecord(
            name=definition.name,
            auth=config_to_auth_payload(definition.auth),
            created_at=now,
            updated_at=now,
        )
        async with self._session_factory() as session:
            session.add(row)
            try:
                await session.commit()
            except IntegrityError as error:
                await session.rollback()
                raise AuthProviderNameTaken(
                    f"Authentication provider '{definition.name}' already exists."
                ) from error
        return definition

    async def update(
        self,
        name: str,
        auth: ManagedAuthProviderConfig,
    ) -> AuthProviderDefinition:
        stmt = select(AuthProviderRecord).where(AuthProviderRecord.name == name)
        async with self._session_factory() as session:
            row = (await session.execute(stmt)).scalar_one_or_none()
            if row is None:
                raise AuthProviderNotFound(f"Unknown authentication provider '{name}'.")
            row.auth = config_to_auth_payload(auth)
            row.updated_at = datetime.now(UTC)
            await session.commit()
            return self._to_definition(row)

    async def dependent_server_names(self, name: str) -> builtins.list[str]:
        stmt = (
            select(ServerConfig.name)
            .where(ServerConfig.auth_provider == name)
            .order_by(ServerConfig.name)
        )
        async with self._session_factory() as session:
            return list((await session.execute(stmt)).scalars().all())

    async def delete(self, name: str) -> None:
        async with self._session_factory() as session:
            row = await session.get(AuthProviderRecord, name)
            if row is None:
                raise AuthProviderNotFound(f"Unknown authentication provider '{name}'.")
            dependent = await self._dependent_server_names(session, name)
            if dependent:
                raise AuthProviderInUse(name, dependent)
            await session.execute(
                delete(AuthProviderRecord).where(AuthProviderRecord.name == name)
            )
            try:
                await session.commit()
            except IntegrityError as error:
                await session.rollback()
                dependent = await self._dependent_server_names(session, name)
                raise AuthProviderInUse(name, dependent) from error

    @staticmethod
    async def _dependent_server_names(session, name: str) -> builtins.list[str]:
        stmt = (
            select(ServerConfig.name)
            .where(ServerConfig.auth_provider == name)
            .order_by(ServerConfig.name)
        )
        return list((await session.execute(stmt)).scalars().all())

    @staticmethod
    def _to_definition(row: AuthProviderRecord) -> AuthProviderDefinition:
        return AuthProviderDefinition.model_validate(
            {"name": row.name, "auth": row.auth}
        )


AuthProviderRepository = AuthProvidersRepository
