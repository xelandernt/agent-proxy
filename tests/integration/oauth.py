from dataclasses import dataclass

import niquests


@dataclass(frozen=True)
class TokenResponse:
    access_token: str
    token_type: str
    scope: str


def request_password_grant_token(
    *,
    auth_server_url: str,
    client_id: str = "local-mcp-client",
    username: str = "admin",
    password: str = "admin",
    scope: str = "mcp.access",
) -> TokenResponse:
    token_url = f"{auth_server_url}/protocol/openid-connect/token"
    payload = {
        "client_id": client_id,
        "username": username,
        "password": password,
        "grant_type": "password",
        "scope": scope,
    }
    with niquests.Session(timeout=10.0) as session:
        resp = session.post(token_url, data=payload)
    resp.raise_for_status()
    data = resp.json()
    return TokenResponse(
        access_token=str(data["access_token"]),
        token_type=str(data.get("token_type", "Bearer")),
        scope=str(data.get("scope", "")),
    )
