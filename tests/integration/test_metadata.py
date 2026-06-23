import pytest


@pytest.mark.integration
def test_protected_resource_metadata_returns_protected_metadata(client):
    resp = client.get(
        "/.well-known/oauth-protected-resource/mcp/playwright",
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["resource"] == "http://localhost:8008/mcp/playwright"
    assert len(data["authorization_servers"]) == 1
    assert "mcp.access" in data["scopes_supported"]
    assert data["resource_name"] == "playwright"


@pytest.mark.integration
def test_protected_resource_metadata_authorization_server_is_keycloak_issuer(
    client, keycloak_details
):
    resp = client.get(
        "/.well-known/oauth-protected-resource/mcp/playwright",
    )
    data = resp.json()
    auth_server = data["authorization_servers"][0]
    assert auth_server == keycloak_details.auth_server_url


@pytest.mark.integration
def test_unknown_server_metadata_returns_404(client):
    resp = client.get(
        "/.well-known/oauth-protected-resource/mcp/nonexistent",
    )
    assert resp.status_code == 404
