from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

import proxy.app.admin.auth as admin_auth_module
import proxy.app.main as main_module
from proxy.app.main import create_app
from proxy.servers.manager import ServerManager
from proxy.servers.models import McpServerConfig
from proxy.servers.repository import ServerNameTaken, ServerNotFound
from proxy.settings import GatewayConfig
from tests.support import StaticAuthProvider

AUTH = {"Authorization": "Bearer valid-token"}


def server_payload(name: str) -> dict[str, object]:
    return {
        "name": name,
        "description": f"Server {name}",
        "upstream_url": "http://127.0.0.1:9/mcp",
        "verify_upstream_tls": True,
        "auth": {
            "provider": "keycloak",
            "realm_url": "https://identity.example/realms/test",
        },
    }


class InMemoryServersRepository:
    """Dict-backed stand-in for ServersRepository."""

    def __init__(self, servers: list[McpServerConfig] | None = None) -> None:
        self._servers = {server.name: server for server in servers or []}

    async def list(self) -> list[McpServerConfig]:
        return sorted(self._servers.values(), key=lambda server: server.name)

    async def get(self, name: str) -> McpServerConfig | None:
        return self._servers.get(name)

    async def create(self, config: McpServerConfig) -> McpServerConfig:
        if config.name in self._servers:
            raise ServerNameTaken(f"MCP server name '{config.name}' already exists.")
        self._servers[config.name] = config
        return config

    async def update(
        self,
        name: str,
        config: McpServerConfig,
    ) -> McpServerConfig:
        if name not in self._servers:
            raise ServerNotFound(f"Unknown MCP server '{name}'.")
        self._servers[name] = config
        return config

    async def delete(self, name: str) -> None:
        if name not in self._servers:
            raise ServerNotFound(f"Unknown MCP server '{name}'.")
        del self._servers[name]


@pytest.fixture()
def boot_gateway(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    def load_static_provider(
        _config: object,
        *,
        base_url: str,
    ) -> StaticAuthProvider:
        return StaticAuthProvider(base_url=base_url, required_scopes=["mcp"])

    monkeypatch.setattr(admin_auth_module, "load_auth_provider", load_static_provider)
    repository = InMemoryServersRepository(
        [
            McpServerConfig.model_validate(
                {
                    "name": "calendar",
                    "upstream_url": "http://127.0.0.1:9/mcp",
                    "auth": {
                        "provider": "keycloak",
                        "realm_url": "https://identity.example/realms/test",
                    },
                }
            )
        ]
    )
    monkeypatch.setattr(main_module, "ServersRepository", lambda _factory: repository)
    monkeypatch.setattr(main_module, "ServerManager", ServerManager)
    config = GatewayConfig.model_validate(
        {
            "admin": {
                "auth": {
                    "provider": "keycloak",
                    "realm_url": "https://identity.example/realms/test",
                    "client_id": "admin",
                }
            },
        }
    )
    return TestClient(create_app(config))


def test_crud_round_trip(boot_gateway: TestClient) -> None:
    with boot_gateway as client:
        listed = client.get("/api/admin/servers", headers=AUTH)
        assert listed.status_code == 200
        assert [server["name"] for server in listed.json()] == ["calendar"]

        created = client.post(
            "/api/admin/servers", headers=AUTH, json=server_payload("docs")
        )
        assert created.status_code == 201
        assert created.json()["name"] == "docs"
        assert created.json()["description"] == "Server docs"

        listed = client.get("/api/admin/servers", headers=AUTH)
        assert [server["name"] for server in listed.json()] == ["calendar", "docs"]

        updated = client.put(
            "/api/admin/servers/calendar",
            headers=AUTH,
            json={
                "description": "Renamed purpose",
                "upstream_url": "http://127.0.0.1:99/mcp",
                "auth": {
                    "provider": "keycloak",
                    "realm_url": "https://identity.example/realms/test",
                },
            },
        )
        assert updated.status_code == 200
        assert updated.json()["upstream_url"] == "http://127.0.0.1:99/mcp"

        deleted = client.delete("/api/admin/servers/docs", headers=AUTH)
        assert deleted.status_code == 204
        listed = client.get("/api/admin/servers", headers=AUTH)
        assert [server["name"] for server in listed.json()] == ["calendar"]


def test_crud_error_mappings(boot_gateway: TestClient) -> None:
    with boot_gateway as client:
        duplicate = client.post(
            "/api/admin/servers", headers=AUTH, json=server_payload("calendar")
        )
        missing_put = client.put(
            "/api/admin/servers/nope",
            headers=AUTH,
            json={
                "upstream_url": "http://127.0.0.1:9/mcp",
                "auth": {
                    "provider": "keycloak",
                    "realm_url": "https://identity.example/realms/test",
                },
            },
        )
        missing_delete = client.delete("/api/admin/servers/nope", headers=AUTH)
        invalid = server_payload("broken")
        invalid["auth"] = {"provider": "jwt"}
        invalid_config = client.post("/api/admin/servers", headers=AUTH, json=invalid)
        unknown_field = server_payload("extra")
        unknown_field["settings"] = {}
        extra_field = client.post(
            "/api/admin/servers", headers=AUTH, json=unknown_field
        )
        conflicting = server_payload("conflicting")
        conflicting["auth"] = {
            "provider": "jwt",
            "public_key": "key",
            "jwks_uri": "https://identity.example/jwks",
        }
        conflicting_config = client.post(
            "/api/admin/servers", headers=AUTH, json=conflicting
        )
        forwarding = server_payload("forwarding")
        forwarding["forward_client_credentials"] = True
        forwarding_config = client.post(
            "/api/admin/servers", headers=AUTH, json=forwarding
        )

    assert duplicate.status_code == 409
    assert missing_put.status_code == 404
    assert missing_delete.status_code == 404
    assert invalid_config.status_code == 422
    assert extra_field.status_code == 422
    assert conflicting_config.status_code == 422
    assert "not both" in conflicting_config.json()["detail"]
    assert forwarding_config.status_code == 422
    assert "forward_client_credentials" in forwarding_config.json()["detail"]


def test_none_provider_server_with_forwarding(boot_gateway: TestClient) -> None:
    with boot_gateway as client:
        created = client.post(
            "/api/admin/servers",
            headers=AUTH,
            json={
                "name": "relay",
                "description": "Authenticated upstream, no gateway auth",
                "upstream_url": "http://127.0.0.1:9/mcp",
                "auth": {"provider": "none"},
                "forward_client_credentials": True,
            },
        )
        assert created.status_code == 201
        body = created.json()
        assert body["auth"] == {"provider": "none"}
        assert body["forward_client_credentials"] is True

        listed = client.get("/api/admin/servers", headers=AUTH)
        relay = next(server for server in listed.json() if server["name"] == "relay")
        assert relay["auth"] == {"provider": "none"}
        assert relay["forward_client_credentials"] is True
