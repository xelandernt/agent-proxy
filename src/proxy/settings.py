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
    address: str = "127.0.0.1"
    port: int = 8008


class CorsConfig(BaseModel):
    origins: list[str] = Field(default_factory=lambda: ["*"])
    allow_credentials: bool = Field(
        default=False,
        description="Credentials cannot be enabled when all origins are allowed.",
    )
    allow_methods: list[str] = Field(default_factory=lambda: ["*"])
    allow_headers: list[str] = Field(default_factory=lambda: ["*"])


class LogfireConfig(BaseModel):
    token: SecretStr | None = None
    environment: str = "dev"
    service_name: str = "proxy"


class MiddlewareConfig(BaseModel):
    cors: CorsConfig = Field(default_factory=CorsConfig)


class DisabledAuthProviderConfig(BaseModel):
    provider: Literal["disabled"] = "disabled"


class OidcAuthProviderConfig(BaseModel):
    provider: Literal["oidc"] = "oidc"
    issuer: str
    allowed_algorithms: list[str] = Field(default_factory=lambda: ["RS256"])
    clock_skew_seconds: int = Field(default=30, ge=0)
    discovery_ttl_seconds: int = Field(default=3600, ge=60)

    @property
    def issuer_url(self) -> str:
        return self.issuer.rstrip("/")


class EntraIdAuthProviderConfig(BaseModel):
    provider: Literal["entra_id"] = "entra_id"
    authority: str = "https://login.microsoftonline.com"
    tenant_id: str | None = None
    issuer: str | None = None
    allowed_algorithms: list[str] = Field(default_factory=lambda: ["RS256"])
    clock_skew_seconds: int = Field(default=30, ge=0)
    discovery_ttl_seconds: int = Field(default=3600, ge=60)

    @property
    def issuer_url(self) -> str:
        if self.issuer:
            return self.issuer.rstrip("/")
        if self.tenant_id is None:
            raise ValueError(
                "tenant_id must be configured when issuer is not provided."
            )
        return f"{self.authority.rstrip('/')}/{self.tenant_id}/v2.0"

    @model_validator(mode="after")
    def validate_configuration(self) -> "EntraIdAuthProviderConfig":
        _ = self.issuer_url
        return self


AuthProviderConfig = Annotated[
    DisabledAuthProviderConfig | OidcAuthProviderConfig | EntraIdAuthProviderConfig,
    Field(discriminator="provider"),
]


class McpServerConfig(BaseModel):
    name: str = Field(pattern=NAME_PATTERN)
    endpoint: AnyHttpUrl
    resource: str | None = None
    accepted_audiences: list[str] = Field(default_factory=list)
    description: str | None = None
    authorization_scopes: list[str] | None = None
    required_scopes: list[str] | None = None


class McpGroupConfig(BaseModel):
    name: str = Field(pattern=NAME_PATTERN)
    auth: AuthProviderConfig = Field(default_factory=DisabledAuthProviderConfig)
    default_authorization_scopes: list[str] | None = None
    default_required_scopes: list[str] = Field(default_factory=list)
    servers: list[McpServerConfig] = Field(min_length=1)

    def authorization_scopes_for_server(
        self, server: McpServerConfig
    ) -> tuple[str, ...]:
        if server.authorization_scopes is not None:
            configured_scopes = server.authorization_scopes
        elif self.default_authorization_scopes is not None:
            configured_scopes = self.default_authorization_scopes
        else:
            configured_scopes = self.required_scopes_for_server(server)
        return tuple(sorted(set(configured_scopes)))

    def required_scopes_for_server(self, server: McpServerConfig) -> tuple[str, ...]:
        configured_scopes = (
            self.default_required_scopes
            if server.required_scopes is None
            else server.required_scopes
        )
        return tuple(sorted(set(configured_scopes)))

    @model_validator(mode="after")
    def validate_protected_server_resources(self) -> "McpGroupConfig":
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
    group: McpGroupConfig
    server: McpServerConfig


class McpConfig(BaseModel):
    groups: list[McpGroupConfig] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_unique_names(self) -> "McpConfig":
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
        for group in self.groups:
            for server in group.servers:
                if server.name == name:
                    return ResolvedMcpServer(group=group, server=server)
        return None


class ProxyConfig(ProxyBaseSettings):
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
        return self.mcp.get_server(name)


CONFIG: Final[ProxyConfig] = ProxyConfig()
