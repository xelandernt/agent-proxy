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
    """Runtime state for the proxy application.

    Attributes:
        config: The loaded proxy configuration.
        session_database: Database connection for session ownership bindings.
        auth_providers: Registry mapping group names to auth providers.
    """

    config: ProxyConfig
    session_database: SessionDatabase
    auth_providers: dict[str, AuthProvider]


def build_app_runtime(config: ProxyConfig) -> AppRuntime:
    """Build the application runtime from a configuration.

    Creates the session database instance and builds the auth provider
    registry from the configured MCP groups.

    Args:
        config: The proxy configuration.

    Returns:
        An AppRuntime instance ready for use.
    """
    return AppRuntime(
        config=config,
        session_database=SessionDatabase(database_url=config.database.url),
        auth_providers=build_auth_provider_registry(config.mcp.groups),
    )


def get_runtime(request: Request) -> AppRuntime:
    """Extract the AppRuntime from the current request's app state.

    Args:
        request: The incoming HTTP request.

    Returns:
        The AppRuntime stored in the application state.
    """
    return cast(AppRuntime, request.app.state.runtime)


RuntimeDep = Annotated[AppRuntime, Depends(get_runtime)]


async def get_async_session(runtime: RuntimeDep) -> AsyncIterator[AsyncSession]:
    """Provide an async SQLAlchemy session for dependency injection.

    Args:
        runtime: The application runtime.

    Yields:
        An async SQLAlchemy session.
    """
    async with runtime.session_database.session_factory() as session:
        yield session


AsyncSessionDep = Annotated[AsyncSession, Depends(get_async_session)]
