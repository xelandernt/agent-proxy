from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest

from tests.integration.keycloak import KeycloakContainer


@pytest.fixture(scope="session")
def keycloak_realm_url() -> Iterator[str]:
    realm_file = Path(__file__).parents[2] / "resources" / "keycloak" / "realm.json"
    with KeycloakContainer(realm_file) as keycloak:
        yield keycloak.realm_url
