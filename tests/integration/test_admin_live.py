from __future__ import annotations

from collections.abc import AsyncIterator

import httpx2
import pytest

import proxy.servers.app as servers_app_module
from proxy.app.main import create_app
from proxy.providers import AuthProviderConfig
from proxy.servers.manager import ServerManager
from proxy.servers.models import McpServerConfig
from proxy.settings import GatewayConfig
from tests.integration.helpers import seed_servers_async
from tests.integration.test_gateway import modern_headers, modern_request
from tests.support import StaticAuthProvider


def keycloak_server(
    name: str,
    upstream_url: str = "http://127.0.0.1:9/mcp",
) -> McpServerConfig:
    return McpServerConfig.model_validate(
        {
            "name": name,
            "upstream_url": upstream_url,
            "auth": {
                "provider": "keycloak",
                "realm_url": "https://identity.example/realms/test",
            },
        }
    )


@pytest.fixture(autouse=True)
def use_static_auth_provider(monkeypatch: pytest.MonkeyPatch) -> None:
    def load_static_provider(
        _config: AuthProviderConfig,
        *,
        base_url: str,
    ) -> StaticAuthProvider:
        return StaticAuthProvider(base_url=base_url, required_scopes=["mcp"])

    monkeypatch.setattr(servers_app_module, "load_auth_provider", load_static_provider)


@pytest.fixture()
async def live_client(
    postgres_url: str,
) -> AsyncIterator[tuple[httpx2.AsyncClient, ServerManager]]:
    await seed_servers_async(postgres_url, [keycloak_server("calendar")])
    config = GatewayConfig.model_validate(
        {
            "public_base_url": "https://gateway.example",
            "database": {"url": postgres_url},
        }
    )
    app = create_app(config)
    async with app.router.lifespan_context(app):
        transport = httpx2.ASGITransport(app=app)
        async with httpx2.AsyncClient(
            transport=transport,
            base_url="https://gateway.example",
        ) as client:
            yield client, app.state.server_manager


async def discovery(client: httpx2.AsyncClient) -> list[str]:
    response = await client.get("/.well-known/mcp-servers")
    assert response.status_code == 200
    return [server["name"] for server in response.json()["servers"]]


async def test_create_server_becomes_discoverable_and_reachable_without_restart(
    live_client: tuple[httpx2.AsyncClient, ServerManager],
) -> None:
    client, manager = live_client
    assert await discovery(client) == ["calendar"]

    await manager.create(keycloak_server("new-server"))
    assert await discovery(client) == ["calendar", "new-server"]

    response = await client.post(
        "/new-server/mcp",
        headers=modern_headers("server/discover"),
        json=modern_request("server/discover"),
    )
    assert response.status_code == 401
    assert response.headers["www-authenticate"].startswith("Bearer")


async def test_delete_server_disappears_without_restart(
    live_client: tuple[httpx2.AsyncClient, ServerManager],
) -> None:
    client, manager = live_client
    await manager.create(keycloak_server("doomed"))
    assert await discovery(client) == ["calendar", "doomed"]

    await manager.delete("doomed")
    assert await discovery(client) == ["calendar"]

    response = await client.post(
        "/doomed/mcp",
        headers=modern_headers("server/discover"),
        json=modern_request("server/discover"),
    )
    assert response.status_code == 404


async def test_update_remounts_with_new_upstream(
    live_client: tuple[httpx2.AsyncClient, ServerManager],
) -> None:
    client, manager = live_client
    updated = keycloak_server("calendar", upstream_url="http://127.0.0.1:99/mcp")

    await manager.update("calendar", updated)

    assert await discovery(client) == ["calendar"]
    assert manager.get("calendar") == updated
    response = await client.post(
        "/calendar/mcp",
        headers=modern_headers("server/discover"),
        json=modern_request("server/discover"),
    )
    assert response.status_code == 401


async def test_create_with_duplicate_name_raises_and_leaves_gateway_untouched(
    live_client: tuple[httpx2.AsyncClient, ServerManager],
) -> None:
    client, manager = live_client

    with pytest.raises(ValueError):
        await manager.create(keycloak_server("calendar"))

    assert await discovery(client) == ["calendar"]
    assert len(manager.snapshot()) == 1


async def test_repeated_create_delete_churn_leaks_no_routes(
    live_client: tuple[httpx2.AsyncClient, ServerManager],
) -> None:
    client, manager = live_client
    for index in range(5):
        await manager.create(keycloak_server(f"churn-{index}"))
        await manager.delete(f"churn-{index}")

    assert await discovery(client) == ["calendar"]
    assert len(manager.snapshot()) == 1
