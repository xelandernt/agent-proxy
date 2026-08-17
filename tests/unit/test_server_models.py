from __future__ import annotations

import pytest
from pydantic import ValidationError

from proxy.servers.models import McpServerConfig


def server(**overrides: object) -> McpServerConfig:
    values: dict[str, object] = {
        "name": "calendar",
        "upstream_url": "https://upstream.example/mcp",
    }
    values.update(overrides)
    return McpServerConfig.model_validate(values)


def test_server_defaults_to_no_gateway_authentication() -> None:
    assert server().auth_provider is None


def test_server_rejects_inline_auth_configuration() -> None:
    with pytest.raises(ValidationError, match="extra_forbidden"):
        server(auth={"provider": "keycloak"})


def test_forwarding_requires_an_unlinked_server() -> None:
    assert server(forward_client_credentials=True).forward_client_credentials

    with pytest.raises(ValidationError, match="forward_client_credentials"):
        server(auth_provider="keycloak", forward_client_credentials=True)
