from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from testcontainers.community.postgres import PostgresContainer

from tests.integration.keycloak import KeycloakContainer

POSTGRES_IMAGE = "postgres:17-alpine"


@pytest.fixture(scope="session")
def keycloak_realm_url() -> Iterator[str]:
    realm_file = Path(__file__).parents[2] / "resources" / "keycloak" / "realm.json"
    with KeycloakContainer(realm_file) as keycloak:
        yield keycloak.realm_url


@pytest.fixture(scope="session")
def postgres_url() -> Iterator[str]:
    with PostgresContainer(POSTGRES_IMAGE) as postgres:
        yield postgres.get_connection_url(driver="asyncpg")
