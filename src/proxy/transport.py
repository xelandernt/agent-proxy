from __future__ import annotations

from functools import partial
from typing import Final

import httpx2
from fastmcp.client.transports import StreamableHttpTransport

SENSITIVE_UPSTREAM_HEADERS: Final = frozenset(
    {"authorization", "cookie", "proxy-authorization"}
)

FORWARDABLE_UPSTREAM_HEADERS: Final = frozenset({"authorization"})


def create_credential_free_http_client(
    headers: dict[str, str] | None = None,
    timeout: httpx2.Timeout | None = None,
    auth: httpx2.Auth | None = None,
    *,
    follow_redirects: bool = True,
    verify: bool = True,
    transport: httpx2.AsyncBaseTransport | None = None,
    forward_client_credentials: bool = False,
    **_: object,
) -> httpx2.AsyncClient:
    """Create the upstream client without ambient credentials.

    FastMCP's proxy transport supplies the incoming ``Authorization`` header to
    this factory. By default the gateway discards it, along with cookies and
    proxy credentials, so a gateway-issued token never leaks to the upstream.
    With ``forward_client_credentials`` set, the incoming ``Authorization``
    header is relayed instead — the passthrough mode for servers whose
    upstream already authenticates the client itself. Cookies and proxy
    credentials remain stripped in every mode. The ``auth`` argument is
    accepted for compatibility with FastMCP's client-factory protocol but is
    never applied.
    """

    del auth
    if forward_client_credentials:
        excluded = SENSITIVE_UPSTREAM_HEADERS - FORWARDABLE_UPSTREAM_HEADERS
    else:
        excluded = SENSITIVE_UPSTREAM_HEADERS
    safe_headers = {
        name: value
        for name, value in (headers or {}).items()
        if name.lower() not in excluded
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
    forward_client_credentials: bool = False,
    http_transport: httpx2.AsyncBaseTransport | None = None,
) -> StreamableHttpTransport:
    """Create a modern HTTP transport with the credential firewall installed.

    The firewall strips credentials by default; pass
    ``forward_client_credentials=True`` to relay the caller's ``Authorization``
    header to the upstream instead.
    """

    return StreamableHttpTransport(
        upstream_url,
        httpx_client_factory=partial(
            create_credential_free_http_client,
            verify=verify_tls,
            transport=http_transport,
            forward_client_credentials=forward_client_credentials,
        ),
    )
