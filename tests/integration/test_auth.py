import niquests
import pytest

from proxy.app.auth import OidcAuthProvider, TokenValidationError
from proxy.app.main import create_app
from proxy.app.mcp import sessions as _sessions_module
from proxy.settings import (
    Config,
    ConfigHost,
    ConfigLogfire,
    ConfigMcp,
    ConfigMcpGroup,
    ConfigMcpServer,
    ConfigDatabase,
    ConfigMiddleware,
    ConfigOidcAuthProvider,
)


@pytest.mark.integration
def test_missing_bearer_token_returns_401(client):
    resp = client.post(
        "/mcp/playwright", json={"jsonrpc": "2.0", "id": 1, "method": "initialize"}
    )
    assert resp.status_code == 401
    assert "WWW-Authenticate" in resp.headers


@pytest.mark.integration
def test_invalid_bearer_token_returns_401(client):
    headers = {"Authorization": "Bearer invalid-token"}
    resp = client.post(
        "/mcp/playwright",
        json={"jsonrpc": "2.0", "id": 1, "method": "initialize"},
        headers=headers,
    )
    assert resp.status_code == 401
    assert "WWW-Authenticate" in resp.headers


@pytest.mark.integration
def test_malformed_auth_header_returns_401(client):
    headers = {"Authorization": "Basic dGVzdDp0ZXN0"}
    resp = client.post(
        "/mcp/playwright",
        json={"jsonrpc": "2.0", "id": 1, "method": "initialize"},
        headers=headers,
    )
    assert resp.status_code == 401


@pytest.mark.integration
def test_valid_token_succeeds(client, auth_header):
    resp = client.post(
        "/mcp/playwright",
        json={
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2025-03-26",
                "capabilities": {},
                "clientInfo": {"name": "test", "version": "0.1.0"},
            },
        },
        headers=auth_header,
    )
    assert resp.status_code in (200, 201)


@pytest.mark.integration
def test_get_with_valid_token(client, auth_header):
    resp = client.get(
        "/mcp/playwright",
        headers=auth_header,
    )
    assert resp.status_code in (200, 400, 405)


@pytest.mark.integration
def test_delete_with_valid_token(client, auth_header):
    resp = client.delete(
        "/mcp/playwright",
        headers=auth_header,
    )
    assert resp.status_code in (200, 400, 405)


@pytest.mark.integration
def test_wrong_audience_token_returns_401(bearer_token, keycloak_details):
    issuer = keycloak_details.auth_server_url
    provider = OidcAuthProvider(ConfigOidcAuthProvider(issuer=issuer))
    server = ConfigMcpServer(
        name="test-server",
        resource="http://unrecognized-resource/mcp",
        endpoint="http://localhost:1/mcp",
    )
    with pytest.raises(TokenValidationError, match="audience"):
        provider.authenticate_token(
            bearer_token,
            server=server,
        )


@pytest.mark.integration
def test_missing_scope_returns_403_through_proxy(auth_header, test_config):
    config = Config(
        host=ConfigHost(address="127.0.0.1", port=0),
        logfire=ConfigLogfire(token=None),
        middleware=ConfigMiddleware(),
        database=ConfigDatabase(
            driver="postgresql+asyncpg",
            address=test_config.database.address,
            port=test_config.database.port,
            username=test_config.database.username,
            password=test_config.database.password,
            database=test_config.database.database,
            sslmode=None,
        ),
        mcp=ConfigMcp(
            groups=[
                ConfigMcpGroup(
                    name="playwright",
                    auth=ConfigOidcAuthProvider(
                        issuer=test_config.mcp.groups[0].auth.issuer,
                    ),
                    default_required_scopes=["nonexistent.scope"],
                    servers=[
                        ConfigMcpServer(
                            name="playwright",
                            resource="http://localhost:8008/mcp/playwright",
                            endpoint=str(test_config.mcp.groups[0].servers[0].endpoint),
                        ),
                    ],
                ),
            ],
        ),
    )
    _sessions_module._DATABASE_CACHE = None
    app = create_app(config=config)
    with niquests.Session(app=app, base_url="asgi://default", timeout=30.0) as sess:
        resp = sess.post(
            "/mcp/playwright",
            json={
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2025-03-26",
                    "capabilities": {},
                    "clientInfo": {"name": "missing-scope", "version": "0.1.0"},
                },
            },
            headers=auth_header,
        )
    assert resp.status_code == 403
    assert "WWW-Authenticate" in resp.headers
    www_auth = resp.headers["WWW-Authenticate"]
    assert "insufficient_scope" in www_auth
    assert "nonexistent.scope" in www_auth
