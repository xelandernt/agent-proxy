from __future__ import annotations

import os
from pathlib import Path

import pytest
from pydantic import ValidationError

from proxy.settings import (
    CONFIG_FILE_ENV,
    GatewayConfig,
    load_config,
)


def test_gateway_requires_at_least_one_server() -> None:
    with pytest.raises(ValidationError, match="servers"):
        GatewayConfig.model_validate({})


def test_gateway_derives_server_base_url() -> None:
    config = GatewayConfig.model_validate(
        {
            "public_base_url": "https://gateway.example/root/",
            "servers": [
                {
                    "name": "calendar",
                    "upstream_url": "http://calendar.internal/mcp",
                    "auth": {
                        "provider": "keycloak",
                        "realm_url": "https://identity.example/realms/test",
                    },
                }
            ],
        }
    )

    assert config.server_base_url(config.servers[0]) == (
        "https://gateway.example/root/calendar"
    )


def test_gateway_accepts_logfire_configuration() -> None:
    config = GatewayConfig.model_validate(
        {
            "logfire": {
                "token": "secret-token",
                "environment": "production",
                "service_name": "mcp-gateway",
            },
            "servers": [
                {
                    "name": "calendar",
                    "upstream_url": "http://calendar.internal/mcp",
                    "auth": {
                        "provider": "keycloak",
                        "realm_url": "https://identity.example/realms/test",
                    },
                }
            ],
        }
    )

    assert config.logfire.token is not None
    assert config.logfire.token.get_secret_value() == "secret-token"
    assert config.logfire.environment == "production"
    assert config.logfire.service_name == "mcp-gateway"


def test_server_names_must_be_unique() -> None:
    server = {
        "name": "calendar",
        "upstream_url": "http://calendar.internal/mcp",
        "auth": {
            "provider": "keycloak",
            "realm_url": "https://identity.example/realms/test",
        },
    }

    with pytest.raises(ValidationError, match="must be unique"):
        GatewayConfig.model_validate({"servers": [server, server]})


def test_provider_rejects_unknown_constructor_fields() -> None:
    with pytest.raises(ValidationError, match="public_base_url"):
        GatewayConfig.model_validate(
            {
                "servers": [
                    {
                        "name": "calendar",
                        "upstream_url": "http://calendar.internal/mcp",
                        "auth": {
                            "provider": "keycloak",
                            "realm_url": "https://identity.example/realms/test",
                            "public_base_url": "https://wrong.example",
                        },
                    }
                ]
            }
        )


def test_load_config_from_selected_yaml(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    for name in os.environ:
        if name.startswith("PROXY__"):
            monkeypatch.delenv(name)
    config_file = tmp_path / "gateway.yaml"
    config_file.write_text(
        """
public_base_url: https://gateway.example
servers:
  - name: calendar
    upstream_url: http://calendar.internal/mcp
    auth:
      provider: keycloak
      realm_url: https://identity.example/realms/test
""".lstrip()
    )
    monkeypatch.setenv(CONFIG_FILE_ENV, str(config_file))

    config = load_config()

    assert config.servers[0].name == "calendar"
