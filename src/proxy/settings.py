import os
from dataclasses import dataclass
from pathlib import Path
from typing import Annotated, Final, Literal

from pydantic import AnyHttpUrl, BaseModel, Field, SecretStr, model_validator
from pydantic_settings import (
    BaseSettings,
    PydanticBaseSettingsSource,
    SettingsConfigDict,
    YamlConfigSettingsSource,
)
from sqlalchemy.engine import URL

CONFIG_DIRECTORY = ".proxy"
CONFIG_FILE_ENV = "PROXY_CONFIG_FILE"
DEFAULT_CONFIG_FILE = Path(CONFIG_DIRECTORY) / "config.yaml"
NAME_PATTERN = r"^[a-z0-9][a-z0-9-]*$"


class ProxyBaseSettings(BaseSettings):
    """Base settings class with custom YAML config source support."""

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


class HostConfig(BaseModel):
    """Configuration for the HTTP server binding address and port."""

    address: str = "127.0.0.1"
    port: int = 8008


class CorsConfig(BaseModel):
    """CORS middleware configuration."""

    origins: list[str] = Field(default_factory=lambda: ["*"])
    allow_credentials: bool = Field(
        default=False,
        description="Credentials cannot be enabled when all origins are allowed.",
    )
    allow_methods: list[str] = Field(default_factory=lambda: ["*"])
    allow_headers: list[str] = Field(default_factory=lambda: ["*"])


class LogfireConfig(BaseModel):
    """Logfire observability configuration."""

    token: SecretStr | None = None
    environment: str = "dev"
    service_name: str = "proxy"


class MiddlewareConfig(BaseModel):
    """Middleware stack configuration."""

    cors: CorsConfig = Field(default_factory=CorsConfig)


class DisabledAuthProviderConfig(BaseModel):
    """Auth provider configuration that disables authentication."""

    provider: Literal["disabled"] = "disabled"


class OidcAuthProviderConfig(BaseModel):
    """OIDC-compliant authentication provider configuration."""

    provider: Literal["oidc"] = "oidc"
    issuer: str
    allowed_algorithms: list[str] = Field(default_factory=lambda: ["RS256"])
    clock_skew_seconds: int = Field(default=30, ge=0)
    discovery_ttl_seconds: int = Field(default=3600, ge=60)

    @property
    def issuer_url(self) -> str:
        """The OIDC issuer URL, with trailing slash stripped."""
        return self.issuer.rstrip("/")


class EntraIdAuthProviderConfig(BaseModel):
    """Microsoft Entra ID (Azure AD) authentication provider configuration."""

    provider: Literal["entra_id"] = "entra_id"
    authority: str = "https://login.microsoftonline.com"
    tenant_id: str | None = None
    issuer: str | None = None
    allowed_algorithms: list[str] = Field(default_factory=lambda: ["RS256"])
    clock_skew_seconds: int = Field(default=30, ge=0)
    discovery_ttl_seconds: int = Field(default=3600, ge=60)

    @property
    def issuer_url(self) -> str:
        """Resolve the effective issuer URL.

        Uses the explicitly configured ``issuer`` if set, otherwise
        constructs the URL from ``authority`` + ``tenant_id`` + ``v2.0``.

        Returns:
            The issuer URL with trailing slash stripped.

        Raises:
            ValueError: If neither ``issuer`` nor ``tenant_id`` is set.
        """
        if self.issuer:
            return self.issuer.rstrip("/")
        if self.tenant_id is None:
            raise ValueError(
                "tenant_id must be configured when issuer is not provided."
            )
        return f"{self.authority.rstrip('/')}/{self.tenant_id}/v2.0"

    @model_validator(mode="after")
    def validate_configuration(self) -> "EntraIdAuthProviderConfig":
        """Validate that a usable issuer URL can be resolved."""
        _ = self.issuer_url
        return self


AuthProviderConfig = Annotated[
    DisabledAuthProviderConfig | OidcAuthProviderConfig | EntraIdAuthProviderConfig,
    Field(discriminator="provider"),
]


class McpServerConfig(BaseModel):
    """Configuration for a single upstream MCP server."""

    name: str = Field(pattern=NAME_PATTERN)
    endpoint: AnyHttpUrl
    resource: str | None = None
    accepted_audiences: list[str] = Field(default_factory=list)
    description: str | None = None
    authorization_scopes: list[str] | None = None
    required_scopes: list[str] | None = None


class McpGroupConfig(BaseModel):
    """Configuration for a group of MCP servers sharing an auth provider."""

    name: str = Field(pattern=NAME_PATTERN)
    auth: AuthProviderConfig = Field(default_factory=DisabledAuthProviderConfig)
    default_authorization_scopes: list[str] | None = None
    default_required_scopes: list[str] = Field(default_factory=list)
    servers: list[McpServerConfig] = Field(min_length=1)

    def authorization_scopes_for_server(
        self, server: McpServerConfig
    ) -> tuple[str, ...]:
        """Return the scopes advertised for a server in resource metadata.

        Falls back from server-specific to group default to required scopes.

        Args:
            server: The MCP server configuration.

        Returns:
            A sorted tuple of unique scope strings.
        """
        if server.authorization_scopes is not None:
            configured_scopes = server.authorization_scopes
        elif self.default_authorization_scopes is not None:
            configured_scopes = self.default_authorization_scopes
        else:
            configured_scopes = self.required_scopes_for_server(server)
        return tuple(sorted(set(configured_scopes)))

    def required_scopes_for_server(self, server: McpServerConfig) -> tuple[str, ...]:
        """Return the scopes required to access a server.

        Falls back from server-specific to group default.

        Args:
            server: The MCP server configuration.

        Returns:
            A sorted tuple of unique scope strings.
        """
        configured_scopes = (
            self.default_required_scopes
            if server.required_scopes is None
            else server.required_scopes
        )
        return tuple(sorted(set(configured_scopes)))

    @model_validator(mode="after")
    def validate_protected_server_resources(self) -> "McpGroupConfig":
        """Ensure all servers in a protected group have a resource URL configured."""
        if isinstance(self.auth, DisabledAuthProviderConfig):
            return self

        missing_resources = [
            server.name for server in self.servers if server.resource is None
        ]
        if missing_resources:
            missing = ", ".join(sorted(missing_resources))
            raise ValueError(
                "Protected MCP servers must configure a canonical resource URL. "
                f"Missing resource for: {missing}."
            )
        return self


class DatabaseConfig(BaseModel):
    """Database connection configuration."""

    driver: str = "postgresql+asyncpg"
    address: str = "127.0.0.1"
    port: int = 5432
    username: str = "postgres"
    password: SecretStr = SecretStr("password")
    database: str = "agent_proxy"
    sslmode: str | None = None
    options: dict[str, str] = Field(default_factory=dict)

    @property
    def url(self) -> str:
        """Build the full SQLAlchemy database URL from the individual fields.

        Returns:
            The database URL as a string, with the password rendered inline.
        """
        query = self.options.copy()
        if self.sslmode is not None:
            query["sslmode"] = self.sslmode
        return URL.create(
            drivername=self.driver,
            username=self.username,
            password=self.password.get_secret_value(),
            host=self.address,
            port=self.port,
            database=self.database,
            query=query,
        ).render_as_string(hide_password=False)


@dataclass(frozen=True)
class ResolvedMcpServer:
    """A resolved MCP server with its group context.

    Attributes:
        group: The MCP group configuration the server belongs to.
        server: The individual MCP server configuration.
    """

    group: McpGroupConfig
    server: McpServerConfig


class McpConfig(BaseModel):
    """Top-level MCP configuration containing all server groups."""

    groups: list[McpGroupConfig] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_unique_names(self) -> "McpConfig":
        """Validate that group and server names are unique across the config."""
        group_names: set[str] = set()
        server_names: set[str] = set()

        for group in self.groups:
            if group.name in group_names:
                raise ValueError(f"MCP group name '{group.name}' must be unique.")
            group_names.add(group.name)

            for server in group.servers:
                if server.name in server_names:
                    raise ValueError(
                        f"MCP server name '{server.name}' must be unique across groups."
                    )
                server_names.add(server.name)

        return self

    def get_server(self, name: str) -> ResolvedMcpServer | None:
        """Look up a server by name across all groups.

        Args:
            name: The server name to find.

        Returns:
            A resolved server with its group context, or None if not found.
        """
        for group in self.groups:
            for server in group.servers:
                if server.name == name:
                    return ResolvedMcpServer(group=group, server=server)
        return None


class ProxyConfig(ProxyBaseSettings):
    """Root configuration model for the Agent Proxy application.

    Reads from YAML, environment variables, and defaults. Environment
    variables are prefixed with ``PROXY__`` and use ``__`` as the nested
    delimiter.
    """

    model_config = SettingsConfigDict(
        env_prefix="PROXY__",
        env_nested_delimiter="__",
        case_sensitive=False,
        yaml_file=f"{CONFIG_DIRECTORY}/config.yaml",
        arbitrary_types_allowed=False,
    )
    host: HostConfig = Field(default_factory=HostConfig)
    logfire: LogfireConfig = Field(default_factory=LogfireConfig)
    middleware: MiddlewareConfig = Field(default_factory=MiddlewareConfig)
    strip_headers: set[str] = Field(
        description="Set of HTTP headers to remove from proxied requests and responses.",
        default_factory=lambda: {
            "connection",
            "keep-alive",
            "proxy-authenticate",
            "proxy-authorization",
            "te",
            "trailer",
            "transfer-encoding",
            "upgrade",
        },
    )
    database: DatabaseConfig = Field(default_factory=DatabaseConfig)
    mcp: McpConfig = Field(default_factory=McpConfig)

    def get_server(self, name: str) -> ResolvedMcpServer | None:
        """Look up a server by name.

        Delegates to ``McpConfig.get_server``.

        Args:
            name: The server name to find.

        Returns:
            A resolved server with its group context, or None.
        """
        return self.mcp.get_server(name)


CONFIG: Final[ProxyConfig] = ProxyConfig()
