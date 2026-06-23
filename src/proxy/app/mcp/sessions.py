from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Annotated, Protocol

from fastapi import Depends
from loguru import logger
from sqlalchemy import String, delete
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from proxy.app.mcp.dependencies import ConfigDep
from proxy.settings import ConfigDatabase


@dataclass(frozen=True)
class SessionOwner:
    issuer: str
    subject: str


class SessionOwnershipConflictError(Exception):
    pass


class SessionRegistry(Protocol):
    async def bind(
        self,
        *,
        server_name: str,
        session_id: str,
        owner: SessionOwner,
        client_id: str | None,
    ) -> None: ...

    async def get(
        self, *, server_name: str, session_id: str
    ) -> SessionOwner | None: ...

    async def remove(self, *, server_name: str, session_id: str) -> None: ...


class Base(DeclarativeBase):
    pass


class SessionBinding(Base):
    __tablename__ = "mcp_session_bindings"

    server_name: Mapped[str] = mapped_column(String, primary_key=True)
    session_id: Mapped[str] = mapped_column(String, primary_key=True)
    issuer: Mapped[str] = mapped_column(String, nullable=False)
    subject: Mapped[str] = mapped_column(String, nullable=False)
    client_id: Mapped[str | None] = mapped_column(String, nullable=True)


class SessionRegistryDatabase:
    def __init__(self, *, database_url: str) -> None:
        self._engine: AsyncEngine = create_async_engine(
            database_url, pool_pre_ping=True
        )
        self._session_factory = async_sessionmaker(
            self._engine,
            expire_on_commit=False,
        )

    async def startup(self) -> None:
        async with self._engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)

    async def shutdown(self) -> None:
        await self._engine.dispose()

    @property
    def session_factory(self) -> async_sessionmaker[AsyncSession]:
        return self._session_factory


_DATABASE_CACHE: tuple[str, SessionRegistryDatabase] | None = None


def get_session_registry_database(
    config: ConfigDatabase,
) -> SessionRegistryDatabase:
    global _DATABASE_CACHE

    database_url = config.url
    if _DATABASE_CACHE is None or _DATABASE_CACHE[0] != database_url:
        _DATABASE_CACHE = (
            database_url,
            SessionRegistryDatabase(database_url=database_url),
        )
    return _DATABASE_CACHE[1]


async def startup_session_registry(config: ConfigDatabase) -> None:
    await get_session_registry_database(config).startup()


async def shutdown_session_registry(config: ConfigDatabase) -> None:
    global _DATABASE_CACHE

    database = get_session_registry_database(config)
    await database.shutdown()
    if _DATABASE_CACHE is not None and _DATABASE_CACHE[1] is database:
        _DATABASE_CACHE = None


async def get_async_session(config: ConfigDep) -> AsyncIterator[AsyncSession]:
    database = get_session_registry_database(config.database)
    async with database.session_factory() as session:
        yield session


AsyncSessionDep = Annotated[AsyncSession, Depends(get_async_session)]


class SqlAlchemySessionRegistry:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def bind(
        self,
        *,
        server_name: str,
        session_id: str,
        owner: SessionOwner,
        client_id: str | None,
    ) -> None:
        self._session.add(
            SessionBinding(
                server_name=server_name,
                session_id=session_id,
                issuer=owner.issuer,
                subject=owner.subject,
                client_id=client_id,
            )
        )
        try:
            await self._session.commit()
            return
        except IntegrityError:
            await self._session.rollback()

        existing_binding = await self._session.get(
            SessionBinding,
            {"server_name": server_name, "session_id": session_id},
        )
        if existing_binding is None:
            raise

        existing_owner = SessionOwner(
            issuer=existing_binding.issuer,
            subject=existing_binding.subject,
        )
        if existing_owner != owner:
            logger.warning(
                "Protected MCP session ownership conflict server={server_name} "
                "existing_issuer={existing_issuer} existing_subject={existing_subject} "
                "request_issuer={request_issuer} "
                "request_subject={request_subject} existing_client_id={existing_client_id} "
                "request_client_id={request_client_id}",
                server_name=server_name,
                existing_issuer=existing_binding.issuer,
                existing_subject=existing_binding.subject,
                request_issuer=owner.issuer,
                request_subject=owner.subject,
                existing_client_id=existing_binding.client_id,
                request_client_id=client_id,
            )
            raise SessionOwnershipConflictError(
                f"Protected session for server '{server_name}' is already bound to a different principal."
            )
        if existing_binding.client_id != client_id:
            existing_binding.client_id = client_id
            await self._session.commit()

    async def get(self, *, server_name: str, session_id: str) -> SessionOwner | None:
        binding = await self._session.get(
            SessionBinding,
            {"server_name": server_name, "session_id": session_id},
        )
        if binding is None:
            return None
        return SessionOwner(
            issuer=binding.issuer,
            subject=binding.subject,
        )

    async def remove(self, *, server_name: str, session_id: str) -> None:
        await self._session.execute(
            delete(SessionBinding).where(
                SessionBinding.server_name == server_name,
                SessionBinding.session_id == session_id,
            )
        )
        await self._session.commit()


async def get_session_registry(session: AsyncSessionDep) -> SessionRegistry:
    return SqlAlchemySessionRegistry(session)


SessionRegistryDep = Annotated[SessionRegistry, Depends(get_session_registry)]
