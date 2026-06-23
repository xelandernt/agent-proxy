import asyncio

import asyncpg
import niquests
import pytest


@pytest.mark.integration
def test_postgres_connection_details(postgres_details):
    assert postgres_details.host
    assert postgres_details.port > 0
    assert postgres_details.username == "postgres"
    assert postgres_details.password == "postgres"
    assert postgres_details.dbname == "agent_proxy"


@pytest.mark.integration
def test_postgres_connectivity(postgres_details):
    async def _check():
        conn = await asyncpg.connect(
            host=postgres_details.host,
            port=postgres_details.port,
            user=postgres_details.username,
            password=postgres_details.password,
            database=postgres_details.dbname,
        )
        version = await conn.fetchval("SELECT version()")
        await conn.close()
        return version

    version = asyncio.run(_check())
    assert "PostgreSQL" in version


@pytest.mark.integration
def test_keycloak_connection_details(keycloak_details):
    assert keycloak_details.host
    assert keycloak_details.port > 0
    assert "realms/agent-proxy" in keycloak_details.auth_server_url


@pytest.mark.integration
def test_keycloak_openid_discovery(keycloak_details):
    url = f"{keycloak_details.auth_server_url}/.well-known/openid-configuration"
    resp = niquests.get(url, timeout=10)
    assert resp.status_code == 200
    data = resp.json()
    assert data["issuer"] == keycloak_details.auth_server_url


@pytest.mark.integration
def test_playwright_mcp_connection_details(playwright_mcp_details):
    assert playwright_mcp_details.host
    assert playwright_mcp_details.port > 0
    assert "/mcp" not in playwright_mcp_details.endpoint_url


@pytest.mark.integration
def test_playwright_mcp_http_endpoint(playwright_mcp_details):
    resp = niquests.get(f"{playwright_mcp_details.endpoint_url}/mcp", timeout=10)
    assert resp.status_code is not None and resp.status_code < 500
