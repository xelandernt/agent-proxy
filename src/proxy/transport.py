from __future__ import annotations

from typing import Final

import httpx2
from fastmcp.client.transports import StreamableHttpTransport

SENSITIVE_UPSTREAM_HEADERS: Final = frozenset(
    {"authorization", "cookie", "proxy-authorization"}
)


def create_credential_free_http_client(
    headers: dict[str, str] | None = None,
    timeout: httpx2.Timeout | None = None,
    auth: httpx2.Auth | None = None,
    *,
    follow_redirects: bool = True,
    verify: bool = True,
    transport: httpx2.AsyncBaseTransport | None = None,
) -> httpx2.AsyncClient:
    """Create the upstream client without caller or ambient credentials.

    FastMCP's proxy transport supplies the incoming ``Authorization`` header to
    this factory. The gateway intentionally discards it, along with cookies and
    proxy credentials. The ``auth`` argument is accepted for compatibility with
    FastMCP's client-factory protocol but is never applied.
    """

    del auth
    safe_headers = {
        name: value
        for name, value in (headers or {}).items()
        if name.lower() not in SENSITIVE_UPSTREAM_HEADERS
    }
    return httpx2.AsyncClient(
        headers=safe_headers,
        timeout=timeout or httpx2.Timeout(30.0, read=3600.0),
        follow_redirects=follow_redirects,
        verify=verify,
        trust_env=False,
        transport=transport,
    )


def create_upstream_transport(
    upstream_url: str,
    *,
    verify_tls: bool = True,
    http_transport: httpx2.AsyncBaseTransport | None = None,
) -> StreamableHttpTransport:
    """Create a modern HTTP transport with the credential firewall installed."""

    def client_factory(
        headers: dict[str, str] | None = None,
        timeout: httpx2.Timeout | None = None,
        auth: httpx2.Auth | None = None,
        **options: object,
    ) -> httpx2.AsyncClient:
        follow_redirects = options.get("follow_redirects", True)
        if not isinstance(follow_redirects, bool):
            raise TypeError("follow_redirects must be a boolean")
        return create_credential_free_http_client(
            headers=headers,
            timeout=timeout,
            auth=auth,
            follow_redirects=follow_redirects,
            verify=verify_tls,
            transport=http_transport,
        )

    return StreamableHttpTransport(
        upstream_url,
        httpx_client_factory=client_factory,
    )
