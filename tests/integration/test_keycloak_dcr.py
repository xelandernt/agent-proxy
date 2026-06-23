import json
import base64

import niquests
import pytest


@pytest.mark.integration
def test_anonymous_dcr_creates_client(keycloak_details):
    dcr_url = f"{keycloak_details.auth_server_url}/clients-registrations/openid-connect"
    payload = {
        "client_name": "test-dcr-client",
        "redirect_uris": ["http://localhost:8000/callback"],
        "token_endpoint_auth_method": "none",
    }
    resp = niquests.post(dcr_url, json=payload, timeout=10)
    assert resp.status_code == 201
    data = resp.json()
    assert "client_id" in data
    assert data["client_id"]
    assert "client_secret" not in data


@pytest.mark.integration
def test_dcr_with_client_id_rejected(keycloak_details):
    dcr_url = f"{keycloak_details.auth_server_url}/clients-registrations/openid-connect"
    payload = {
        "client_id": "user-chosen-id",
        "client_name": "test-dcr-rejected",
        "redirect_uris": ["http://localhost:8000/callback"],
        "token_endpoint_auth_method": "none",
    }
    resp = niquests.post(dcr_url, json=payload, timeout=10)
    assert resp.status_code == 400


@pytest.mark.integration
def test_dcr_client_can_request_mcp_access(keycloak_details):
    dcr_url = f"{keycloak_details.auth_server_url}/clients-registrations/openid-connect"
    payload = {
        "client_name": "test-dcr-scope",
        "redirect_uris": ["http://localhost:8000/callback"],
        "token_endpoint_auth_method": "none",
        "grant_types": ["authorization_code", "password", "refresh_token"],
    }
    resp = niquests.post(dcr_url, json=payload, timeout=10)
    assert resp.status_code == 201, f"DCR failed: {resp.text[:300]}"
    data = resp.json()
    client_id = data["client_id"]
    assert client_id

    token_url = f"{keycloak_details.auth_server_url}/protocol/openid-connect/token"
    token_resp = niquests.post(
        token_url,
        data={
            "client_id": client_id,
            "username": "admin",
            "password": "admin",
            "grant_type": "password",
            "scope": "mcp.access",
        },
        timeout=10,
    )
    assert token_resp.status_code == 200, (
        f"Token request failed: {token_resp.text[:300]}"
    )
    access_token = token_resp.json()["access_token"]
    parts = access_token.split(".")
    claims = json.loads(base64.urlsafe_b64decode(parts[1] + "=="))

    scope_claim = claims.get("scope", "")
    assert "mcp.access" in scope_claim, f"Token missing mcp.access scope: {scope_claim}"
