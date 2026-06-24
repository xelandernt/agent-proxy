from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from proxy.sessions.models import Base


class SessionDatabase:
    """Manages the async SQLAlchemy engine and session factory.

    Handles database lifecycle: creating tables on startup and disposing
    the connection pool on shutdown.

    Args:
        database_url: The SQLAlchemy database URL string.
    """

    def __init__(self, *, database_url: str) -> None:
        self._engine: AsyncEngine = create_async_engine(
            database_url, pool_pre_ping=True
        )
        self._session_factory = async_sessionmaker(
            self._engine,
            expire_on_commit=False,
        )

    async def startup(self) -> None:
        """Create all database tables on application startup."""
        async with self._engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)

    async def shutdown(self) -> None:
        """Dispose the database connection pool on shutdown."""
        await self._engine.dispose()

    @property
    def session_factory(self) -> async_sessionmaker[AsyncSession]:
        """The async session factory for creating database sessions."""
        return self._session_factory
