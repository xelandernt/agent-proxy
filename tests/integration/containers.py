import pathlib
import time
import types
from dataclasses import dataclass

import niquests
from testcontainers.core.container import DockerContainer
from testcontainers.postgres import PostgresContainer

REALM_JSON = (
    pathlib.Path(__file__).parent.parent.parent
    / "resources"
    / "keycloak"
    / "realm.json"
)


@dataclass(frozen=True)
class PostgresDetails:
    host: str
    port: int
    username: str
    password: str
    dbname: str


@dataclass(frozen=True)
class KeycloakDetails:
    host: str
    port: int
    auth_server_url: str


@dataclass(frozen=True)
class PlaywrightMcpDetails:
    host: str
    port: int
    endpoint_url: str


class PostgresContainerWrapper:
    def __init__(self) -> None:
        self._container = PostgresContainer(
            image="postgres:17-alpine",
            username="postgres",
            password="postgres",
            dbname="agent_proxy",
        )

    def __enter__(self) -> PostgresDetails:
        self._container.__enter__()
        return self._get_details()

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: types.TracebackType | None,
    ) -> None:
        self._container.__exit__(exc_type, exc_val, exc_tb)

    def _get_details(self) -> PostgresDetails:
        return PostgresDetails(
            host=self._container.get_container_host_ip(),
            port=int(self._container.get_exposed_port(5432)),
            username=self._container.username,
            password=self._container.password,
            dbname=self._container.dbname,
        )


class KeycloakContainerWrapper:
    def __init__(self) -> None:
        self._container = (
            DockerContainer("quay.io/keycloak/keycloak:26.4")
            .with_exposed_ports(8080)
            .with_env("KC_BOOTSTRAP_ADMIN_USERNAME", "admin")
            .with_env("KC_BOOTSTRAP_ADMIN_PASSWORD", "admin")
            .with_env("KC_HEALTH_ENABLED", "true")
            .with_volume_mapping(
                str(REALM_JSON), "/opt/keycloak/data/import/realm.json", "ro"
            )
            .with_command("start-dev --import-realm")
        )

    def __enter__(self) -> KeycloakDetails:
        self._container.__enter__()
        host = self._container.get_container_host_ip()
        port = int(self._container.get_exposed_port(8080))
        details = KeycloakDetails(
            host=host,
            port=port,
            auth_server_url=f"http://{host}:{port}/realms/agent-proxy",
        )
        self._wait_for_readiness(details)
        return details

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: types.TracebackType | None,
    ) -> None:
        self._container.__exit__(exc_type, exc_val, exc_tb)

    def _wait_for_readiness(
        self, details: KeycloakDetails, timeout: float = 120.0
    ) -> None:
        url = f"{details.auth_server_url}/.well-known/openid-configuration"
        deadline = time.monotonic() + timeout
        last_exc: Exception | None = None
        while time.monotonic() < deadline:
            try:
                resp = niquests.get(url, timeout=5)
                if resp.status_code == 200:
                    return
            except Exception as exc:
                last_exc = exc
            time.sleep(1)
        raise TimeoutError(f"Keycloak did not become ready at {url}") from last_exc


class PlaywrightMCPContainerWrapper:
    def __init__(self) -> None:
        self._container = (
            DockerContainer("mcr.microsoft.com/playwright/mcp")
            .with_exposed_ports(8931)
            .with_kwargs(entrypoint=["node"])
            .with_command(
                [
                    "/app/cli.js",
                    "--headless",
                    "--browser",
                    "chromium",
                    "--no-sandbox",
                    "--port",
                    "8931",
                    "--host",
                    "0.0.0.0",
                    "--allowed-hosts",
                    "*",
                ]
            )
        )

    def __enter__(self) -> PlaywrightMcpDetails:
        self._container.__enter__()
        host = self._container.get_container_host_ip()
        port = int(self._container.get_exposed_port(8931))
        details = PlaywrightMcpDetails(
            host=host,
            port=port,
            endpoint_url=f"http://{host}:{port}",
        )
        self._wait_for_readiness(details)
        return details

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: types.TracebackType | None,
    ) -> None:
        self._container.__exit__(exc_type, exc_val, exc_tb)

    def _wait_for_readiness(
        self, details: PlaywrightMcpDetails, timeout: float = 60.0
    ) -> None:
        deadline = time.monotonic() + timeout
        last_exc: Exception | None = None
        while time.monotonic() < deadline:
            try:
                resp = niquests.get(f"{details.endpoint_url}/mcp", timeout=5)
                if resp.status_code is not None and resp.status_code < 500:
                    return
            except Exception as exc:
                last_exc = exc
            time.sleep(1)
        raise TimeoutError("Playwright MCP did not become ready") from last_exc
