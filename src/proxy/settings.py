from typing import Final, List, Optional

from pydantic import BaseModel, Field, SecretStr
from pydantic_settings import (
    BaseSettings,
    PydanticBaseSettingsSource,
    YamlConfigSettingsSource,
    SettingsConfigDict,
)

CONFIG_DIRECTORY = ".proxy"


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
        return (
            init_settings,
            env_settings,
            YamlConfigSettingsSource(settings_cls=settings_cls),
            file_secret_settings,
            dotenv_settings,
        )


class ConfigHost(BaseModel):
    """Configuration for a host."""

    address: str = "127.0.0.1"
    port: int = 8001


class ConfigCors(BaseModel):
    """Cors configuration."""

    origins: List[str] = ["http://localhost:3000"]
    allow_credentials: bool = Field(
        default=True,
        description="If this is true, then `*` in origins will be ignored as per CORS spec.",
    )
    allow_methods: List[str] = ["*"]
    allow_headers: List[str] = ["*"]


class ConfigLogfire(BaseModel):
    """Configuration for observability."""

    token: Optional[SecretStr] = None
    environment: str = "dev"
    service_name: str = "proxy"


class ConfigMiddleware(BaseModel):
    """Middleware configuration."""

    cors: ConfigCors = ConfigCors()


class Config(_Settings):
    model_config = SettingsConfigDict(
        env_prefix="PROXY__",
        env_nested_delimiter="__",
        case_sensitive=False,
        yaml_file=f"{CONFIG_DIRECTORY}/config.yaml",
        arbitrary_types_allowed=False,
    )
    host: ConfigHost = ConfigHost()
    logfire: ConfigLogfire = ConfigLogfire()
    middleware: ConfigMiddleware = ConfigMiddleware()


CONFIG: Final[Config] = Config()
