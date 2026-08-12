from __future__ import annotations

from collections.abc import AsyncIterator

import httpx2
import pytest

import proxy.app.admin.auth as admin_auth_module
import proxy.servers.app as servers_app_module
from proxy.app.main import create_app
from proxy.servers.models import McpServerConfig
from proxy.settings import GatewayConfig
from tests.integration.helpers import seed_servers_async
from tests.integration.test_gateway import modern_headers, modern_request
from tests.support import StaticAuthProvider

AUTH = {"Authorization": "Bearer valid-token"}


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


def server_payload(
    name: str,
    upstream_url: str = "http://127.0.0.1:9/mcp",
) -> dict[str, object]:
    return {
        "name": name,
        "description": f"Server {name}",
        "upstream_url": upstream_url,
        "verify_upstream_tls": True,
        "auth": {
            "provider": "keycloak",
            "realm_url": "https://identity.example/realms/test",
        },
    }


def update_payload(
    upstream_url: str = "http://127.0.0.1:9/mcp",
) -> dict[str, object]:
    payload = server_payload("ignored")
    payload.pop("name")
    return {**payload, "upstream_url": upstream_url}


@pytest.fixture(autouse=True)
def use_static_auth_providers(monkeypatch: pytest.MonkeyPatch) -> None:
    def load_static_provider(
        _config: object,
        *,
        base_url: str,
    ) -> StaticAuthProvider:
        return StaticAuthProvider(base_url=base_url, required_scopes=["mcp"])

    monkeypatch.setattr(servers_app_module, "load_auth_provider", load_static_provider)
    monkeypatch.setattr(admin_auth_module, "load_auth_provider", load_static_provider)


@pytest.fixture()
async def admin_client(postgres_url: str) -> AsyncIterator[httpx2.AsyncClient]:
    await seed_servers_async(postgres_url, [keycloak_server("calendar")])
    config = GatewayConfig.model_validate(
        {
            "public_base_url": "https://gateway.example",
            "database": {"url": postgres_url},
            "admin": {
                "auth": {
                    "provider": "keycloak",
                    "realm_url": "https://identity.example/realms/test",
                    "client_id": "agent-proxy-admin-ui",
                }
            },
        }
    )
    app = create_app(config)
    async with app.router.lifespan_context(app):
        transport = httpx2.ASGITransport(app=app)
        async with httpx2.AsyncClient(
            transport=transport,
            base_url="https://gateway.example",
        ) as client:
            yield client


async def listed_names(client: httpx2.AsyncClient) -> list[str]:
    response = await client.get("/api/admin/servers", headers=AUTH)
    assert response.status_code == 200
    return [server["name"] for server in response.json()]


async def test_full_crud_lifecycle(admin_client: httpx2.AsyncClient) -> None:
    client = admin_client
    assert await listed_names(client) == ["calendar"]

    created = await client.post(
        "/api/admin/servers", headers=AUTH, json=server_payload("new-server")
    )
    assert created.status_code == 201, created.text
    assert created.json()["name"] == "new-server"
    assert await listed_names(client) == ["calendar", "new-server"]

    discovery = await client.get("/.well-known/mcp-servers")
    assert [server["name"] for server in discovery.json()["servers"]] == [
        "calendar",
        "new-server",
    ]
    mounted = await client.post(
        "/new-server/mcp",
        headers=modern_headers("server/discover"),
        json=modern_request("server/discover"),
    )
    assert mounted.status_code == 401

    updated = await client.put(
        "/api/admin/servers/calendar",
        headers=AUTH,
        json=update_payload(upstream_url="http://127.0.0.1:99/mcp"),
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["upstream_url"] == "http://127.0.0.1:99/mcp"

    deleted = await client.delete("/api/admin/servers/new-server", headers=AUTH)
    assert deleted.status_code == 204
    assert await listed_names(client) == ["calendar"]
    gone = await client.post(
        "/new-server/mcp",
        headers=modern_headers("server/discover"),
        json=modern_request("server/discover"),
    )
    assert gone.status_code == 404
    discovery = await client.get("/.well-known/mcp-servers")
    assert [server["name"] for server in discovery.json()["servers"]] == ["calendar"]


async def test_duplicate_create_returns_409(admin_client: httpx2.AsyncClient) -> None:
    response = await admin_client.post(
        "/api/admin/servers", headers=AUTH, json=server_payload("calendar")
    )

    assert response.status_code == 409
    assert "already exists" in response.json()["detail"]


async def test_unknown_update_and_delete_return_404(
    admin_client: httpx2.AsyncClient,
) -> None:
    client = admin_client
    updated = await client.put(
        "/api/admin/servers/missing",
        headers=AUTH,
        json=update_payload(),
    )
    deleted = await client.delete("/api/admin/servers/missing", headers=AUTH)

    assert updated.status_code == 404
    assert deleted.status_code == 404


async def test_invalid_auth_config_returns_422(
    admin_client: httpx2.AsyncClient,
) -> None:
    payload = server_payload("broken")
    payload["auth"] = {
        "provider": "keycloak",
        "realm_url": "not-a-url",
    }
    response = await admin_client.post("/api/admin/servers", headers=AUTH, json=payload)

    assert response.status_code == 422
    assert "realm_url" in response.text


async def test_auth_schema_discriminates_on_provider(
    admin_client: httpx2.AsyncClient,
) -> None:
    response = await admin_client.get("/api/admin/auth-schema", headers=AUTH)

    assert response.status_code == 200
    schema = response.json()
    assert set(schema["discriminator"]["mapping"]) == {
        "auth0",
        "authkit",
        "aws-cognito",
        "azure",
        "descope",
        "discord",
        "github",
        "google",
        "huggingface",
        "jwt",
        "keycloak",
        "none",
        "oci",
        "propelauth",
        "scalekit",
        "supabase",
        "workos",
    }


async def test_crud_requires_authentication(admin_client: httpx2.AsyncClient) -> None:
    response = await admin_client.get("/api/admin/servers")

    assert response.status_code == 401
