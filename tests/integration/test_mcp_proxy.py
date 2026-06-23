import json

import pytest


def _parse_sse_data(text: str) -> list[dict]:
    results = []
    for line in text.split("\n"):
        if line.startswith("data: "):
            results.append(json.loads(line[6:]))
    return results


@pytest.mark.integration
def test_initialize_returns_server_info(client, auth_header):
    resp = client.post(
        "/mcp/playwright",
        json={
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2025-03-26",
                "capabilities": {},
                "clientInfo": {"name": "test-initialize", "version": "0.1.0"},
            },
        },
        headers=auth_header,
    )
    assert resp.status_code in (200, 201)
    events = _parse_sse_data(resp.text)
    assert len(events) >= 1
    assert events[0].get("jsonrpc") == "2.0"
    assert "result" in events[0]
    assert "serverInfo" in events[0]["result"]


@pytest.mark.integration
def test_initialize_returns_session_id(client, auth_header):
    resp = client.post(
        "/mcp/playwright",
        json={
            "jsonrpc": "2.0",
            "id": 2,
            "method": "initialize",
            "params": {
                "protocolVersion": "2025-03-26",
                "capabilities": {},
                "clientInfo": {"name": "test-session", "version": "0.1.0"},
            },
        },
        headers=auth_header,
    )
    assert resp.status_code in (200, 201)
    assert "mcp-session-id" in resp.headers
    session_id = resp.headers.get("mcp-session-id")
    assert session_id


@pytest.mark.integration
def test_tools_list_after_initialize(client, auth_header):
    init_resp = client.post(
        "/mcp/playwright",
        json={
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2025-03-26",
                "capabilities": {},
                "clientInfo": {"name": "test-tools", "version": "0.1.0"},
            },
        },
        headers=auth_header,
    )
    assert init_resp.status_code in (200, 201)
    session_id = init_resp.headers.get("mcp-session-id")
    assert session_id

    tools_headers = {**auth_header, "mcp-session-id": session_id}
    tools_resp = client.post(
        "/mcp/playwright",
        json={
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/list",
            "params": {},
        },
        headers=tools_headers,
    )
    assert tools_resp.status_code in (200, 201)
    tools_events = _parse_sse_data(tools_resp.text)
    assert len(tools_events) >= 1
    assert "result" in tools_events[0]
    assert "tools" in tools_events[0]["result"]
