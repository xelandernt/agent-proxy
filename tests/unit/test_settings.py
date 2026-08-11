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


def test_gateway_requires_database() -> None:
    with pytest.raises(ValidationError, match="database"):
        GatewayConfig.model_validate({})


def test_gateway_rejects_servers_key() -> None:
    with pytest.raises(ValidationError, match="servers"):
        GatewayConfig.model_validate(
            {
                "database": {
                    "url": "postgresql+asyncpg://proxy:proxy@127.0.0.1:5433/proxy",
                },
                "servers": [],
            }
        )


def test_database_round_trips() -> None:
    config = GatewayConfig.model_validate(
        {
            "database": {
                "url": "postgresql+asyncpg://proxy:proxy@127.0.0.1:5433/proxy",
            },
        }
    )

    assert (
        config.database.url == "postgresql+asyncpg://proxy:proxy@127.0.0.1:5433/proxy"
    )


def test_admin_accepts_auth_provider() -> None:
    config = GatewayConfig.model_validate(
        {
            "database": {
                "url": "postgresql+asyncpg://proxy:proxy@127.0.0.1:5433/proxy",
            },
            "admin": {
                "auth": {
                    "provider": "keycloak",
                    "realm_url": "https://identity.example/realms/test",
                    "client_id": "agent-proxy-admin-ui",
                }
            },
        }
    )

    assert config.admin is not None
    assert config.admin.auth.provider == "keycloak"


def test_admin_rejects_keycloak_without_client_id() -> None:
    with pytest.raises(ValidationError, match="client_id is required"):
        GatewayConfig.model_validate(
            {
                "database": {
                    "url": "postgresql+asyncpg://proxy:proxy@127.0.0.1:5433/proxy",
                },
                "admin": {
                    "auth": {
                        "provider": "keycloak",
                        "realm_url": "https://identity.example/realms/test",
                    }
                },
            }
        )


def test_admin_defaults_to_absent() -> None:
    config = GatewayConfig.model_validate(
        {
            "database": {
                "url": "postgresql+asyncpg://proxy:proxy@127.0.0.1:5433/proxy",
            },
        }
    )

    assert config.admin is None


def test_admin_rejects_unknown_fields() -> None:
    with pytest.raises(ValidationError, match="settings"):
        GatewayConfig.model_validate(
            {
                "database": {
                    "url": "postgresql+asyncpg://proxy:proxy@127.0.0.1:5433/proxy",
                },
                "admin": {
                    "auth": {
                        "provider": "keycloak",
                        "realm_url": "https://identity.example/realms/test",
                        "client_id": "agent-proxy-admin-ui",
                    },
                    "settings": {},
                },
            }
        )


def test_gateway_accepts_logfire_configuration() -> None:
    config = GatewayConfig.model_validate(
        {
            "database": {
                "url": "postgresql+asyncpg://proxy:proxy@127.0.0.1:5433/proxy",
            },
            "logfire": {
                "token": "secret-token",
                "environment": "production",
                "service_name": "mcp-gateway",
            },
        }
    )

    assert config.logfire.token is not None
    assert config.logfire.token.get_secret_value() == "secret-token"
    assert config.logfire.environment == "production"
    assert config.logfire.service_name == "mcp-gateway"


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
database:
  url: postgresql+asyncpg://proxy:proxy@127.0.0.1:5433/proxy
admin:
  auth:
    provider: keycloak
    realm_url: https://identity.example/realms/test
    client_id: agent-proxy-admin-ui
""".lstrip()
    )
    monkeypatch.setenv(CONFIG_FILE_ENV, str(config_file))

    config = load_config()

    assert config.admin is not None
    assert config.admin.auth.provider == "keycloak"
