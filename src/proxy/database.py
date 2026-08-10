from __future__ import annotations

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Declarative base for all gateway persistence models."""


def create_engine(database_url: str) -> AsyncEngine:
    """Create the asynchronous SQLAlchemy engine for a PostgreSQL DSN."""

    return create_async_engine(database_url, pool_pre_ping=True)


def create_session_factory(
    engine: AsyncEngine,
) -> async_sessionmaker[AsyncSession]:
    """Create a session factory bound to the given engine."""

    return async_sessionmaker(engine, expire_on_commit=False)
