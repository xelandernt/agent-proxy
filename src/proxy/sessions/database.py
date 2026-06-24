from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from proxy.sessions.models import Base


class SessionDatabase:
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
