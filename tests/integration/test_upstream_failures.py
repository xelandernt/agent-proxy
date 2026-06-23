import niquests
import pytest


@pytest.mark.integration
def test_protected_request_to_unreachable_upstream(auth_header, test_config):
    import proxy.app.mcp.sessions as _sessions

    _sessions._DATABASE_CACHE = None

    bad_config = test_config.model_copy(deep=True)
    bad_config.mcp.groups[0].servers[0].endpoint = "http://localhost:1/mcp"
    from proxy.app.main import create_app

    bad_app = create_app(config=bad_config)
    with niquests.Session(
        app=bad_app, base_url="asgi://default", timeout=30.0
    ) as bad_client:
        resp = bad_client.post(
            "/mcp/playwright",
            json={
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2025-03-26",
                    "capabilities": {},
                    "clientInfo": {"name": "bad-upstream", "version": "0.1.0"},
                },
            },
            headers=auth_header,
        )
    assert resp.status_code == 502
