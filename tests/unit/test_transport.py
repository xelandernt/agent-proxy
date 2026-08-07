from __future__ import annotations

import pytest

from proxy.transport import create_credential_free_http_client


@pytest.mark.asyncio
async def test_upstream_client_removes_all_incoming_credentials() -> None:
    client = create_credential_free_http_client(
        headers={
            "Authorization": "Bearer front-token",
            "Cookie": "session=front-cookie",
            "Proxy-Authorization": "Basic front-proxy-token",
            "X-Safe": "preserved",
        }
    )
    try:
        assert "authorization" not in client.headers
        assert "cookie" not in client.headers
        assert "proxy-authorization" not in client.headers
        assert client.headers["x-safe"] == "preserved"
    finally:
        await client.aclose()
