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

CONFIG_DIRECTORY = ".proxy"
CONFIG_FILE_ENV = "PROXY_CONFIG_FILE"
DEFAULT_CONFIG_FILE = Path(CONFIG_DIRECTORY) / "config.yaml"
_NAME_PATTERN = r"^[a-z0-9][a-z0-9-]*$"


class _Settings(BaseSettings):
    """Base settings class for all project settings."""

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


class ConfigHost(BaseModel):
    """Configuration for a host."""

    address: str = "127.0.0.1"
    port: int = 8008


class ConfigCors(BaseModel):
    """Cors configuration."""

    origins: list[str] = Field(default_factory=lambda: ["http://localhost:3000"])
    allow_credentials: bool = Field(
        default=True,
        description="If this is true, then `*` in origins will be ignored as per CORS spec.",
    )
    allow_methods: list[str] = Field(default_factory=lambda: ["*"])
    allow_headers: list[str] = Field(default_factory=lambda: ["*"])


class ConfigLogfire(BaseModel):
    """Configuration for observability."""

    token: SecretStr | None = None
    environment: str = "dev"
    service_name: str = "proxy"


class ConfigMiddleware(BaseModel):
    """Middleware configuration."""

    cors: ConfigCors = Field(default_factory=ConfigCors)


class ConfigDisabledAuthProvider(BaseModel):
    """Anonymous passthrough for a group of MCP servers."""

    provider: Literal["disabled"] = "disabled"


class ConfigEntraIdAuthProvider(BaseModel):
    """Azure Entra ID bearer-token validation settings."""

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
    def validate_configuration(self) -> "ConfigEntraIdAuthProvider":
        _ = self.issuer_url
        return self


ConfigAuthProvider = Annotated[
    ConfigDisabledAuthProvider | ConfigEntraIdAuthProvider,
    Field(discriminator="provider"),
]


class ConfigMcpServer(BaseModel):
    """Configuration for an upstream MCP HTTP endpoint."""

    name: str = Field(pattern=_NAME_PATTERN)
    endpoint: AnyHttpUrl
    resource: AnyHttpUrl | None = None
    description: str | None = None
    required_scopes: list[str] | None = None


class ConfigMcpGroup(BaseModel):
    """A group of MCP servers sharing one auth provider."""

    name: str = Field(pattern=_NAME_PATTERN)
    auth: ConfigAuthProvider = Field(default_factory=ConfigDisabledAuthProvider)
    default_required_scopes: list[str] = Field(default_factory=list)
    servers: list[ConfigMcpServer] = Field(min_length=1)

    def required_scopes_for_server(self, server: ConfigMcpServer) -> tuple[str, ...]:
        configured_scopes = (
            self.default_required_scopes
            if server.required_scopes is None
            else server.required_scopes
        )
        return tuple(sorted(set(configured_scopes)))

    @model_validator(mode="after")
    def validate_protected_server_resources(self) -> "ConfigMcpGroup":
        if isinstance(self.auth, ConfigDisabledAuthProvider):
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


@dataclass(frozen=True)
class ResolvedMcpServer:
    group: ConfigMcpGroup
    server: ConfigMcpServer


class ConfigMcp(BaseModel):
    """Grouped MCP backend registry."""

    groups: list[ConfigMcpGroup] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_unique_names(self) -> "ConfigMcp":
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


class Config(_Settings):
    model_config = SettingsConfigDict(
        env_prefix="PROXY__",
        env_nested_delimiter="__",
        case_sensitive=False,
        yaml_file=f"{CONFIG_DIRECTORY}/config.yaml",
        arbitrary_types_allowed=False,
    )
    host: ConfigHost = Field(default_factory=ConfigHost)
    logfire: ConfigLogfire = Field(default_factory=ConfigLogfire)
    middleware: ConfigMiddleware = Field(default_factory=ConfigMiddleware)
    mcp: ConfigMcp = Field(default_factory=ConfigMcp)

    def get_server(self, name: str) -> ResolvedMcpServer | None:
        return self.mcp.get_server(name)


CONFIG: Final[Config] = Config()
