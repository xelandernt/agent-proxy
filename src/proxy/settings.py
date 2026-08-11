from __future__ import annotations

import os
from pathlib import Path
from typing import Final

from pydantic import (
    AnyHttpUrl,
    BaseModel,
    ConfigDict,
    Field,
    SecretStr,
    model_validator,
)
from pydantic_settings import (
    BaseSettings,
    PydanticBaseSettingsSource,
    SettingsConfigDict,
    YamlConfigSettingsSource,
)

from proxy.providers import AuthProviderConfig, KeycloakAuthProviderConfig

CONFIG_DIRECTORY: Final = ".proxy"
CONFIG_FILE_ENV: Final = "PROXY_CONFIG_FILE"
DEFAULT_CONFIG_FILE: Final = Path(CONFIG_DIRECTORY) / "config.yaml"


class HostConfig(BaseModel):
    """HTTP listener settings."""

    model_config = ConfigDict(extra="forbid")

    address: str = "127.0.0.1"
    port: int = Field(default=8008, ge=1, le=65535)


class LogfireConfig(BaseModel):
    """Logfire observability settings."""

    model_config = ConfigDict(extra="forbid")

    token: SecretStr | None = None
    environment: str = "dev"
    service_name: str = "proxy"


class DatabaseConfig(BaseModel):
    """PostgreSQL persistence for server configuration and usage tracing."""

    model_config = ConfigDict(extra="forbid")

    url: str = Field(
        description="Async PostgreSQL DSN (for example postgresql+asyncpg://...)."
    )


class AdminConfig(BaseModel):
    """Runtime administration identity provider."""

    model_config = ConfigDict(extra="forbid")

    auth: AuthProviderConfig

    @model_validator(mode="after")
    def validate_keycloak_client(self) -> AdminConfig:
        if (
            isinstance(self.auth, KeycloakAuthProviderConfig)
            and self.auth.client_id is None
        ):
            raise ValueError(
                "admin.auth.client_id is required for the keycloak provider: "
                "without it the gateway cannot run the browser sign-in flow and "
                "would accept any token from the realm. Use provider 'static' "
                "for username/password or 'jwt' for pasted tokens instead."
            )
        return self


class GatewayConfig(BaseModel):
    """Validated, environment-independent gateway configuration."""

    model_config = ConfigDict(extra="forbid")

    host: HostConfig = Field(default_factory=HostConfig)
    logfire: LogfireConfig = Field(default_factory=LogfireConfig)
    database: DatabaseConfig
    public_base_url: AnyHttpUrl = AnyHttpUrl("http://127.0.0.1:8008")
    cors_origins: list[AnyHttpUrl] = Field(default_factory=list)
    admin: AdminConfig | None = None


class _GatewaySettings(BaseSettings):
    """YAML and environment input model used only by ``load_config``."""

    model_config = SettingsConfigDict(
        env_prefix="PROXY__",
        env_nested_delimiter="__",
        case_sensitive=False,
        extra="forbid",
    )

    host: HostConfig = Field(default_factory=HostConfig)
    logfire: LogfireConfig = Field(default_factory=LogfireConfig)
    database: DatabaseConfig
    public_base_url: AnyHttpUrl = AnyHttpUrl("http://127.0.0.1:8008")
    cors_origins: list[AnyHttpUrl] = Field(default_factory=list)
    admin: AdminConfig | None = None

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        yaml_file = Path(os.getenv(CONFIG_FILE_ENV, str(DEFAULT_CONFIG_FILE)))
        return (
            init_settings,
            env_settings,
            YamlConfigSettingsSource(settings_cls=settings_cls, yaml_file=yaml_file),
            file_secret_settings,
            dotenv_settings,
        )


def load_config() -> GatewayConfig:
    """Load and validate gateway configuration from YAML and environment."""

    settings = _GatewaySettings()
    return GatewayConfig.model_validate(settings.model_dump())
