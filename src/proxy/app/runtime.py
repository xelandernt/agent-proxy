from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Annotated, cast

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from proxy.auth.providers import AuthProvider, build_auth_provider_registry
from proxy.sessions.database import SessionDatabase
from proxy.settings import ProxyConfig


@dataclass(frozen=True)
class AppRuntime:
    config: ProxyConfig
    session_database: SessionDatabase
    auth_providers: dict[str, AuthProvider]


def build_app_runtime(config: ProxyConfig) -> AppRuntime:
    return AppRuntime(
        config=config,
        session_database=SessionDatabase(database_url=config.database.url),
        auth_providers=build_auth_provider_registry(config.mcp.groups),
    )


def get_runtime(request: Request) -> AppRuntime:
    return cast(AppRuntime, request.app.state.runtime)


RuntimeDep = Annotated[AppRuntime, Depends(get_runtime)]


async def get_async_session(runtime: RuntimeDep) -> AsyncIterator[AsyncSession]:
    async with runtime.session_database.session_factory() as session:
        yield session


AsyncSessionDep = Annotated[AsyncSession, Depends(get_async_session)]
