from __future__ import annotations

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.pool import NullPool


class Base(DeclarativeBase):
    """Declarative base for all gateway persistence models."""


def create_engine(database_url: str) -> AsyncEngine:
    """Create the asynchronous SQLAlchemy engine for a PostgreSQL DSN."""

    return create_async_engine(
        database_url,
        poolclass=NullPool,
        pool_pre_ping=True,
    )


def create_session_factory(
    engine: AsyncEngine,
) -> async_sessionmaker[AsyncSession]:
    """Create a session factory bound to the given engine."""

    return async_sessionmaker(engine, expire_on_commit=False)


async def create_all_tables(engine: AsyncEngine) -> None:
    """Create all gateway tables after registering every persistence model."""

    # Model imports are intentionally local: importing the database module
    # should define the shared metadata without importing every feature.
    import proxy.api_keys.models
    import proxy.app.model_usage.models
    import proxy.app.usage.models
    import proxy.app.users.models
    import proxy.auth_providers.persistence
    import proxy.model_deployments.models
    import proxy.model_providers.models
    import proxy.servers.models  # noqa: F401

    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
