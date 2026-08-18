from __future__ import annotations

import os
from pathlib import Path
from typing import Final, Literal

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

from proxy.providers import (
    AdminAuthProviderConfig,
    KeycloakAuthProviderConfig,
    UserAuthProviderConfig,
)

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


class DatabaseConfig(HostConfig):
    """Connection settings shared by database backends."""

    port: int = Field(default=5432, ge=1, le=65535)
    username: SecretStr = SecretStr("user")
    password: SecretStr = SecretStr("password")


class PostgresqlConfig(DatabaseConfig):
    """Configuration for the PostgreSQL database."""

    db_name: str = "proxy"

    @property
    def connection_url(self) -> str:
        """Build the async PostgreSQL DSN from the configured parts."""
        username = self.username.get_secret_value()
        password = self.password.get_secret_value()
        return (
            f"postgresql+asyncpg://{username}:{password}@"
            f"{self.address}:{self.port}/{self.db_name}"
        )


class CorsConfig(BaseModel):
    """Cors configuration."""

    model_config = ConfigDict(extra="forbid")

    origins: list[str] = Field(default_factory=lambda: ["http://localhost:3000"])
    allow_credentials: bool = Field(
        default=True,
        description="If this is true, then `*` in origins will be ignored as per CORS spec.",
    )
    allow_methods: list[str] = Field(default_factory=lambda: ["*"])
    allow_headers: list[str] = Field(default_factory=lambda: ["*"])


class MiddlewareConfig(BaseModel):
    """Middleware configuration."""

    model_config = ConfigDict(extra="forbid")

    cors: CorsConfig = Field(default_factory=CorsConfig)


class AdminConfig(BaseModel):
    """Runtime administration identity provider."""

    model_config = ConfigDict(extra="forbid")

    auth: AdminAuthProviderConfig
    session_cookie_samesite: Literal["strict", "lax", "none"] = Field(
        default="lax",
        description=(
            "SameSite policy for the admin session cookie. 'lax' suits the "
            "default same-site deployment where the admin UI and the gateway "
            "share a site; 'none' is required when the UI is served from a "
            "different site and requires HTTPS. With 'none', state-changing "
            "admin requests are additionally checked against the configured "
            "CORS origins."
        ),
    )

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


class UserConfig(BaseModel):
    """Interactive identity provider for end-user account access."""

    model_config = ConfigDict(extra="forbid")

    auth: UserAuthProviderConfig
    oauth_scopes: list[str] = Field(default_factory=lambda: ["openid", "email"])
    session_cookie_samesite: Literal["strict", "lax", "none"] = Field(
        default="lax",
        description="SameSite policy for the user account session cookie.",
    )

    @model_validator(mode="after")
    def validate_user_auth(self) -> UserConfig:
        if (
            isinstance(self.auth, KeycloakAuthProviderConfig)
            and self.auth.client_id is None
        ):
            raise ValueError(
                "user.auth.client_id is required for the keycloak provider."
            )
        required = {"openid", "email"}
        if not required.issubset(self.oauth_scopes):
            raise ValueError("user.oauth_scopes must include 'openid' and 'email'.")
        if len(self.oauth_scopes) != len(set(self.oauth_scopes)):
            raise ValueError("user.oauth_scopes must not contain duplicates.")
        return self


class ModelGatewayConfig(BaseModel):
    """Security settings for upstream model credentials."""

    model_config = ConfigDict(extra="forbid")

    credential_encryption_key: SecretStr = Field(
        description="URL-safe base64 Fernet key used to encrypt provider credentials.",
    )


class GatewayConfig(BaseModel):
    """Validated, environment-independent gateway configuration."""

    model_config = ConfigDict(extra="forbid")

    host: HostConfig = Field(default_factory=HostConfig)
    logfire: LogfireConfig = Field(default_factory=LogfireConfig)
    postgresql: PostgresqlConfig = Field(default_factory=PostgresqlConfig)
    public_base_url: AnyHttpUrl = AnyHttpUrl("http://127.0.0.1:8008")
    middleware: MiddlewareConfig = Field(default_factory=MiddlewareConfig)
    admin: AdminConfig
    user: UserConfig
    model_gateway: ModelGatewayConfig


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
    postgresql: PostgresqlConfig = Field(default_factory=PostgresqlConfig)
    public_base_url: AnyHttpUrl = AnyHttpUrl("http://127.0.0.1:8008")
    middleware: MiddlewareConfig = Field(default_factory=MiddlewareConfig)
    admin: AdminConfig
    user: UserConfig
    model_gateway: ModelGatewayConfig

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
