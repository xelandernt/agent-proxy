from __future__ import annotations

import asyncio
from collections.abc import Iterator
from pathlib import Path

import pytest
from testcontainers.community.postgres import PostgresContainer

from proxy.database import Base, create_engine
from proxy.settings import PostgresqlConfig
from tests.integration.keycloak import KeycloakContainer

POSTGRES_IMAGE = "postgres:17-alpine"


def _connection_url(parts: dict[str, object]) -> str:
    return PostgresqlConfig.model_validate(parts).connection_url


def reset_database(database_url: str) -> None:
    """Drop every table so the next app boot starts from an empty schema."""

    async def _reset() -> None:
        engine = create_engine(database_url)
        try:
            async with engine.begin() as connection:
                await connection.run_sync(Base.metadata.drop_all)
        finally:
            await engine.dispose()

    asyncio.run(_reset())


@pytest.fixture(scope="session")
def postgresql_container() -> Iterator[dict[str, object]]:
    """Session-wide PostgreSQL container shared by every database test."""
    with PostgresContainer(POSTGRES_IMAGE) as postgres:
        yield {
            "address": postgres.get_container_host_ip(),
            "port": postgres.get_exposed_port(5432),
            "username": postgres.username,
            "password": postgres.password,
            "db_name": postgres.dbname,
        }


@pytest.fixture()
def postgresql(postgresql_container: dict[str, object]) -> dict[str, object]:
    """Per-test reset wrapper around the shared PostgreSQL container."""
    reset_database(_connection_url(postgresql_container))
    return postgresql_container


@pytest.fixture()
def postgresql_url(postgresql: dict[str, object]) -> str:
    """Connection URL for the reset, per-test PostgreSQL database."""
    return _connection_url(postgresql)


@pytest.fixture(scope="session")
def keycloak_realm_url() -> Iterator[str]:
    realm_file = Path(__file__).parents[2] / "resources" / "keycloak" / "realm.json"
    with KeycloakContainer(realm_file) as keycloak:
        yield keycloak.realm_url
