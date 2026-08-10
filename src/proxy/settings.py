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

from proxy.providers import AuthProviderConfig

CONFIG_DIRECTORY: Final = ".proxy"
CONFIG_FILE_ENV: Final = "PROXY_CONFIG_FILE"
DEFAULT_CONFIG_FILE: Final = Path(CONFIG_DIRECTORY) / "config.yaml"
NAME_PATTERN: Final = r"^[a-z0-9][a-z0-9-]*$"


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


class McpServerConfig(BaseModel):
    """One protected modern MCP endpoint and its unauthenticated backend."""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(pattern=NAME_PATTERN)
    description: str = ""
    upstream_url: AnyHttpUrl
    auth: AuthProviderConfig
    verify_upstream_tls: bool = True


class GatewayConfig(BaseModel):
    """Validated, environment-independent gateway configuration."""

    model_config = ConfigDict(extra="forbid")

    host: HostConfig = Field(default_factory=HostConfig)
    logfire: LogfireConfig = Field(default_factory=LogfireConfig)
    public_base_url: AnyHttpUrl = AnyHttpUrl("http://127.0.0.1:8008")
    cors_origins: list[AnyHttpUrl] = Field(default_factory=list)
    servers: list[McpServerConfig] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_unique_server_names(self) -> GatewayConfig:
        seen: set[str] = set()
        for server in self.servers:
            if server.name in seen:
                raise ValueError(f"MCP server name '{server.name}' must be unique.")
            seen.add(server.name)
        return self

    def server_base_url(self, server: McpServerConfig) -> str:
        """Return the public base URL for a mounted FastMCP server."""

        return f"{str(self.public_base_url).rstrip('/')}/{server.name}"


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
    public_base_url: AnyHttpUrl = AnyHttpUrl("http://127.0.0.1:8008")
    cors_origins: list[AnyHttpUrl] = Field(default_factory=list)
    servers: list[McpServerConfig] = Field(min_length=1)

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
