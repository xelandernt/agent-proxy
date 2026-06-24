import threading
import time
from collections.abc import Iterator

import niquests
import pytest
import uvicorn
from fastapi import FastAPI

from proxy.app.main import create_app
from proxy.settings import (
    DatabaseConfig,
    HostConfig,
    LogfireConfig,
    McpConfig,
    McpGroupConfig,
    McpServerConfig,
    MiddlewareConfig,
    OidcAuthProviderConfig,
    ProxyConfig,
)
from tests.integration.containers import (
    KeycloakContainerWrapper,
    KeycloakDetails,
    PlaywrightMCPContainerWrapper,
    PlaywrightMcpDetails,
    PostgresContainerWrapper,
    PostgresDetails,
)
from tests.integration.helpers import find_free_port


class UvicornServerThread(threading.Thread):
    def __init__(self, app: FastAPI, host: str, port: int) -> None:
        super().__init__(daemon=True)
        self.app = app
        self.host = host
        self.port = port
        self._ready = threading.Event()

    def run(self) -> None:
        config = uvicorn.Config(
            self.app,
            host=self.host,
            port=self.port,
            log_level="error",
            lifespan="on",
        )
        self._ready.set()
        server = uvicorn.Server(config)
        server.run()

    def wait_until_ready(self, timeout: float = 30.0) -> str:
        self._ready.wait(timeout=5)
        deadline = time.monotonic() + timeout
        url = f"http://{self.host}:{self.port}"
        while time.monotonic() < deadline:
            try:
                resp = niquests.get(f"{url}/mcp/nonexistent", timeout=5)
                if resp.status_code in (404, 405):
                    return url
            except Exception:
                pass
            time.sleep(0.2)
        raise TimeoutError("Uvicorn server did not become ready")


@pytest.fixture(scope="session")
def postgres_details() -> Iterator[PostgresDetails]:
    with PostgresContainerWrapper() as details:
        yield details


@pytest.fixture(scope="session")
def keycloak_details() -> Iterator[KeycloakDetails]:
    with KeycloakContainerWrapper() as details:
        yield details


@pytest.fixture(scope="session")
def playwright_mcp_details() -> Iterator[PlaywrightMcpDetails]:
    with PlaywrightMCPContainerWrapper() as details:
        yield details


@pytest.fixture(scope="session")
def proxy_port() -> int:
    return find_free_port()


@pytest.fixture(scope="session")
def test_config(
    postgres_details: PostgresDetails,
    keycloak_details: KeycloakDetails,
    playwright_mcp_details: PlaywrightMcpDetails,
    proxy_port: int,
) -> ProxyConfig:
    return ProxyConfig(
        host=HostConfig(address="127.0.0.1", port=proxy_port),
        logfire=LogfireConfig(token=None),
        middleware=MiddlewareConfig(),
        strip_headers={
            "connection",
            "keep-alive",
            "proxy-authenticate",
            "proxy-authorization",
            "te",
            "trailer",
            "transfer-encoding",
            "upgrade",
        },
        database=DatabaseConfig(
            driver="postgresql+asyncpg",
            address=postgres_details.host,
            port=postgres_details.port,
            username=postgres_details.username,
            password=postgres_details.password,
            database=postgres_details.dbname,
            sslmode=None,
        ),
        mcp=McpConfig(
            groups=[
                McpGroupConfig(
                    name="playwright",
                    auth=OidcAuthProviderConfig(
                        issuer=f"{keycloak_details.auth_server_url}",
                    ),
                    default_required_scopes=["mcp.access"],
                    servers=[
                        McpServerConfig(
                            name="playwright",
                            resource="http://localhost:8008/mcp/playwright",
                            endpoint=f"{playwright_mcp_details.endpoint_url}/mcp",
                        ),
                    ],
                ),
            ],
        ),
    )


@pytest.fixture(scope="session")
def app(test_config: ProxyConfig) -> FastAPI:
    return create_app(config=test_config)


@pytest.fixture(scope="session")
def proxy_url(
    app: FastAPI,
    test_config: ProxyConfig,
    proxy_port: int,
) -> Iterator[str]:
    host = test_config.host.address
    thread = UvicornServerThread(app, host=host, port=proxy_port)
    thread.start()
    url = thread.wait_until_ready()
    yield url


@pytest.fixture(scope="session")
def client(proxy_url: str) -> niquests.Session:
    return niquests.Session(base_url=proxy_url, timeout=30.0)


@pytest.fixture
def anonymous_config(postgres_details: PostgresDetails) -> ProxyConfig:
    return ProxyConfig(
        host=HostConfig(address="0.0.0.0", port=0),
        logfire=LogfireConfig(token=None),
        database=DatabaseConfig(
            driver="postgresql+asyncpg",
            address=postgres_details.host,
            port=postgres_details.port,
            username=postgres_details.username,
            password=postgres_details.password,
            database=postgres_details.dbname,
            sslmode=None,
        ),
        mcp=McpConfig(
            groups=[
                McpGroupConfig(
                    name="anonymous",
                    servers=[
                        McpServerConfig(
                            name="anonymous-server",
                            endpoint="http://localhost:1/mcp",
                        ),
                    ],
                ),
            ],
        ),
    )


@pytest.fixture
def anonymous_app(anonymous_config: ProxyConfig) -> FastAPI:
    return create_app(config=anonymous_config)


@pytest.fixture
def anonymous_client(anonymous_app: FastAPI) -> Iterator[niquests.Session]:
    port = find_free_port()
    host = "127.0.0.1"
    thread = UvicornServerThread(anonymous_app, host=host, port=port)
    thread.start()
    url = thread.wait_until_ready()
    session = niquests.Session(base_url=url, timeout=30.0)
    yield session


@pytest.fixture(scope="session")
def bearer_token(keycloak_details: KeycloakDetails) -> str:
    from tests.integration.oauth import request_password_grant_token

    token_response = request_password_grant_token(
        auth_server_url=keycloak_details.auth_server_url,
        client_id="local-mcp-client",
        username="admin",
        password="admin",
        scope="mcp.access",
    )
    return token_response.access_token


@pytest.fixture
def auth_header(bearer_token: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {bearer_token}",
        "Accept": "application/json, text/event-stream",
        "Content-Type": "application/json",
    }
