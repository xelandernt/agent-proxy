import json
import socket
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler

import asyncpg
import niquests
import pytest

from proxy.app.main import create_app
from proxy.app.mcp import sessions as _sessions_module
from tests.integration.containers import KeycloakDetails


def _find_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


def _parse_sse_data(text: str) -> list[dict]:
    results = []
    for line in text.split("\n"):
        if line.startswith("data: "):
            results.append(json.loads(line[6:]))
    return results


async def _count_bindings(postgres_details) -> int:
    conn = await asyncpg.connect(
        host=postgres_details.host,
        port=postgres_details.port,
        user=postgres_details.username,
        password=postgres_details.password,
        database=postgres_details.dbname,
    )
    try:
        row = await conn.fetchrow("SELECT COUNT(*) AS cnt FROM mcp_session_bindings")
        return row["cnt"]
    finally:
        await conn.close()


async def _get_binding(
    postgres_details, server_name: str, session_id: str
) -> dict | None:
    conn = await asyncpg.connect(
        host=postgres_details.host,
        port=postgres_details.port,
        user=postgres_details.username,
        password=postgres_details.password,
        database=postgres_details.dbname,
    )
    try:
        row = await conn.fetchrow(
            "SELECT server_name, session_id, issuer, subject, client_id FROM mcp_session_bindings "
            "WHERE server_name = $1 AND session_id = $2",
            server_name,
            session_id,
        )
        if row:
            return dict(row)
        return None
    finally:
        await conn.close()


def _create_second_principal_token(keycloak_details) -> str:
    keycloak_base = keycloak_details.auth_server_url.replace("/realms/agent-proxy", "")
    master_token_url = f"{keycloak_base}/realms/master/protocol/openid-connect/token"
    admin_resp = niquests.post(
        master_token_url,
        data={
            "client_id": "admin-cli",
            "username": "admin",
            "password": "admin",
            "grant_type": "password",
        },
        timeout=10,
    )
    admin_resp.raise_for_status()
    admin_token = admin_resp.json()["access_token"]

    admin_api_url = f"{keycloak_base}/admin/realms/agent-proxy"
    users_url = f"{admin_api_url}/users"
    user_payload = {
        "username": "second-user",
        "enabled": True,
        "emailVerified": True,
        "email": "second@example.com",
        "firstName": "Second",
        "lastName": "User",
        "credentials": [
            {"type": "password", "value": "second-pass", "temporary": False}
        ],
        "requiredActions": [],
    }
    create_resp = niquests.post(
        users_url,
        json=user_payload,
        headers={"Authorization": f"Bearer {admin_token}"},
        timeout=10,
    )
    if create_resp.status_code == 409:
        user_id_resp = niquests.get(
            f"{users_url}?username=second-user",
            headers={"Authorization": f"Bearer {admin_token}"},
            timeout=10,
        )
        user_id_resp.raise_for_status()
        user_id = user_id_resp.json()[0]["id"]
        niquests.delete(
            f"{users_url}/{user_id}",
            headers={"Authorization": f"Bearer {admin_token}"},
            timeout=10,
        ).raise_for_status()
        create_resp = niquests.post(
            users_url,
            json=user_payload,
            headers={"Authorization": f"Bearer {admin_token}"},
            timeout=10,
        )
    create_resp.raise_for_status()

    token_url = f"{keycloak_details.auth_server_url}/protocol/openid-connect/token"
    token_resp = niquests.post(
        token_url,
        data={
            "client_id": "local-mcp-client",
            "username": "second-user",
            "password": "second-pass",
            "grant_type": "password",
            "scope": "mcp.access",
        },
        timeout=10,
    )
    if token_resp.status_code != 200:
        users_url = f"{admin_api_url}/users?username=second-user"
        user_check = niquests.get(
            users_url,
            headers={"Authorization": f"Bearer {admin_token}"},
            timeout=10,
        )
        user_check_text = (user_check.text or "")[:300]
        raise RuntimeError(
            f"Failed to get token for second-user: {token_resp.status_code} {token_resp.text} "
            f"user_check: {user_check.status_code} {user_check_text}"
        )
    return token_resp.json()["access_token"]


@pytest.fixture
def second_principal_token(keycloak_details: KeycloakDetails) -> str:
    return _create_second_principal_token(keycloak_details)


@pytest.mark.integration
async def test_initialize_binds_session_to_principal(
    client, auth_header, postgres_details
):
    count_before = await _count_bindings(postgres_details)

    resp = client.post(
        "/mcp/playwright",
        json={
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2025-03-26",
                "capabilities": {},
                "clientInfo": {"name": "session-owner-test", "version": "0.1.0"},
            },
        },
        headers=auth_header,
    )
    assert resp.status_code in (200, 201)
    assert "mcp-session-id" in resp.headers
    session_id = resp.headers["mcp-session-id"]

    count_after = await _count_bindings(postgres_details)
    assert count_after == count_before + 1

    binding = await _get_binding(postgres_details, "playwright", session_id)
    assert binding is not None
    assert binding["server_name"] == "playwright"
    assert binding["session_id"] == session_id


@pytest.mark.integration
async def test_same_session_same_principal_succeeds(
    client, auth_header, postgres_details
):
    init_resp = client.post(
        "/mcp/playwright",
        json={
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2025-03-26",
                "capabilities": {},
                "clientInfo": {"name": "same-principal", "version": "0.1.0"},
            },
        },
        headers=auth_header,
    )
    assert init_resp.status_code in (200, 201)
    session_id = init_resp.headers.get("mcp-session-id")

    count_before_follow = await _count_bindings(postgres_details)
    binding_before = await _get_binding(postgres_details, "playwright", session_id)
    assert binding_before is not None

    follow_up = client.post(
        "/mcp/playwright",
        json={
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/list",
            "params": {},
        },
        headers={**auth_header, "mcp-session-id": session_id},
    )
    assert follow_up.status_code in (200, 201)

    count_after_follow = await _count_bindings(postgres_details)
    assert count_after_follow == count_before_follow

    binding_after = await _get_binding(postgres_details, "playwright", session_id)
    assert binding_after is not None
    assert binding_after["issuer"] == binding_before["issuer"]
    assert binding_after["subject"] == binding_before["subject"]


@pytest.mark.integration
async def test_different_principal_rejected(
    client, auth_header, second_principal_token, postgres_details
):
    init_resp = client.post(
        "/mcp/playwright",
        json={
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2025-03-26",
                "capabilities": {},
                "clientInfo": {"name": "diff-principal", "version": "0.1.0"},
            },
        },
        headers=auth_header,
    )
    assert init_resp.status_code in (200, 201)
    session_id = init_resp.headers.get("mcp-session-id")
    assert session_id

    other_headers = {
        "Authorization": f"Bearer {second_principal_token}",
        "Accept": "application/json, text/event-stream",
        "Content-Type": "application/json",
        "mcp-session-id": session_id,
    }

    rejected = client.post(
        "/mcp/playwright",
        json={
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/list",
            "params": {},
        },
        headers=other_headers,
    )
    assert rejected.status_code == 404

    binding = await _get_binding(postgres_details, "playwright", session_id)
    assert binding is not None
    assert binding["issuer"] != ""
    assert binding["subject"] != ""


@pytest.mark.integration
async def test_delete_removes_session_binding(
    auth_header, test_config, postgres_details
):
    mock_session_id = "mock-session-for-delete"

    class MockMcpHandler(BaseHTTPRequestHandler):
        def do_POST(self):
            length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(length)
            req = json.loads(body) if body else {}
            if req.get("method") == "initialize":
                self.send_response(200)
                self.send_header("Content-Type", "text/event-stream")
                self.send_header("mcp-session-id", mock_session_id)
                self.end_headers()
                self.wfile.write(
                    b'event: message\ndata: {"jsonrpc":"2.0","id":1,"result":{"protocolVersion":"2025-03-26","capabilities":{},"serverInfo":{"name":"mock","version":"1.0"}}}\n\n'
                )
            else:
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(b'{"jsonrpc":"2.0","id":1,"result":{}}')

        def do_DELETE(self):
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(b"{}")

        def log_message(self, *args):
            pass

    mock_port = _find_free_port()
    server = HTTPServer(("127.0.0.1", mock_port), MockMcpHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    config = test_config.model_copy(deep=True)
    config.mcp.groups[0].servers[0].endpoint = f"http://127.0.0.1:{mock_port}/mcp"
    _sessions_module._DATABASE_CACHE = None
    mock_app = create_app(config=config)
    with niquests.Session(
        app=mock_app, base_url="asgi://default", timeout=10.0
    ) as sess:
        init_resp = sess.post(
            "/mcp/playwright",
            json={
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2025-03-26",
                    "capabilities": {},
                    "clientInfo": {"name": "delete-binding", "version": "0.1.0"},
                },
            },
            headers=auth_header,
        )
        assert init_resp.status_code in (200, 201)

        binding_before = await _get_binding(
            postgres_details, "playwright", mock_session_id
        )
        assert binding_before is not None

        delete_resp = sess.delete(
            "/mcp/playwright",
            headers={**auth_header, "mcp-session-id": mock_session_id},
        )
        assert 200 <= delete_resp.status_code < 300

    binding_after = await _get_binding(postgres_details, "playwright", mock_session_id)
    assert binding_after is None
    server.shutdown()
