from __future__ import annotations

from pathlib import Path

from testcontainers.core.container import DockerContainer
from testcontainers.core.wait_strategies import HttpWaitStrategy

KEYCLOAK_IMAGE = "quay.io/keycloak/keycloak:26.6.0"
KEYCLOAK_PORT = 8080
TEST_REALM = "agent-proxy"


class KeycloakContainer(DockerContainer):
    """Keycloak 26.6 with the gateway integration realm imported."""

    def __init__(self, realm_file: Path) -> None:
        super().__init__(KEYCLOAK_IMAGE)
        self.with_exposed_ports(KEYCLOAK_PORT)
        self.with_env("KC_BOOTSTRAP_ADMIN_USERNAME", "admin")
        self.with_env("KC_BOOTSTRAP_ADMIN_PASSWORD", "admin")
        self.with_env("KC_IMPORT_REALM_STRATEGY", "OVERWRITE_EXISTING")
        self.with_command("start-dev --import-realm")
        self.with_volume_mapping(
            realm_file.resolve(),
            "/opt/keycloak/data/import/realm.json",
            "ro",
        )
        self.waiting_for(
            HttpWaitStrategy(
                KEYCLOAK_PORT,
                f"/realms/{TEST_REALM}/.well-known/openid-configuration",
            )
            .for_status_code(200)
            .with_startup_timeout(120)
        )

    @property
    def realm_url(self) -> str:
        host = self.get_container_host_ip()
        port = self.get_exposed_port(KEYCLOAK_PORT)
        return f"http://{host}:{port}/realms/{TEST_REALM}"
