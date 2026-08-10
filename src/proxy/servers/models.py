from __future__ import annotations

from datetime import datetime
from typing import Final, cast

from pydantic import (
    AnyHttpUrl,
    BaseModel,
    ConfigDict,
    Field,
    SecretStr,
    TypeAdapter,
)
from sqlalchemy import JSON, Boolean, DateTime, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from proxy.database import Base
from proxy.providers import AuthProviderConfig

NAME_PATTERN: Final = r"^[a-z0-9][a-z0-9-]*$"

AUTH_PROVIDER_ADAPTER: Final = TypeAdapter(AuthProviderConfig)


class McpServerConfig(BaseModel):
    """One protected modern MCP endpoint and its unauthenticated backend."""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(pattern=NAME_PATTERN)
    description: str = ""
    upstream_url: AnyHttpUrl
    auth: AuthProviderConfig
    verify_upstream_tls: bool = True


def server_base_url(public_base_url: str, name: str) -> str:
    """Return the public base URL for a mounted FastMCP server."""

    return f"{public_base_url.rstrip('/')}/{name}"


class ServerConfig(Base):
    """Persisted runtime MCP server configuration."""

    __tablename__ = "servers"

    name: Mapped[str] = mapped_column(String(100), primary_key=True)
    description: Mapped[str] = mapped_column(String(255), default="")
    upstream_url: Mapped[str] = mapped_column(String(2048))
    verify_upstream_tls: Mapped[bool] = mapped_column(Boolean, default=True)
    auth: Mapped[dict] = mapped_column(JSON().with_variant(JSONB, "postgresql"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    def to_config(self) -> McpServerConfig:
        """Convert the row to a validated runtime config, failing on corrupt auth."""

        return McpServerConfig(
            name=self.name,
            description=self.description,
            upstream_url=self.upstream_url,
            verify_upstream_tls=self.verify_upstream_tls,
            auth=AUTH_PROVIDER_ADAPTER.validate_python(self.auth),
        )


def config_to_auth_payload(config: McpServerConfig) -> dict:
    """Serialize a server's auth provider to its plaintext JSONB payload."""

    payload = _jsonable(AUTH_PROVIDER_ADAPTER.dump_python(config.auth, mode="python"))
    return cast(dict, payload)


def _jsonable(value: object) -> object:
    """Recursively convert pydantic values into plain JSON-serializable data."""

    if isinstance(value, SecretStr):
        return value.get_secret_value()
    if isinstance(value, AnyHttpUrl):
        return str(value)
    if isinstance(value, dict):
        return {key: _jsonable(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_jsonable(item) for item in value]
    return value
