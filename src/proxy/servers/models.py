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
    model_validator,
)
from sqlalchemy import JSON, Boolean, DateTime, String, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from proxy.database import Base
from proxy.providers import ServerAuthProviderConfig

NAME_PATTERN: Final = r"^[a-z0-9][a-z0-9-]*$"
SECRET_MASK: Final = "**********"

AUTH_PROVIDER_ADAPTER: Final = TypeAdapter(ServerAuthProviderConfig)


class McpServerConfig(BaseModel):
    """One protected modern MCP endpoint and its unauthenticated backend."""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(pattern=NAME_PATTERN, max_length=100)
    description: str = Field(default="", max_length=255)
    upstream_url: AnyHttpUrl = Field(max_length=2048)
    auth: ServerAuthProviderConfig
    verify_upstream_tls: bool = True
    forward_client_credentials: bool = False

    @model_validator(mode="after")
    def validate_forward_client_credentials(self) -> McpServerConfig:
        if self.forward_client_credentials and self.auth.provider != "none":
            raise ValueError(
                "forward_client_credentials requires auth provider 'none': "
                "with gateway authentication the incoming Authorization is a "
                "gateway-issued token and must not be relayed upstream."
            )
        return self


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
    forward_client_credentials: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default=text("FALSE")
    )
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
            forward_client_credentials=self.forward_client_credentials,
            auth=AUTH_PROVIDER_ADAPTER.validate_python(self.auth),
        )


def config_to_auth_payload(config: McpServerConfig) -> dict:
    """Serialize a server's auth provider to its plaintext JSONB payload."""

    payload = _jsonable(AUTH_PROVIDER_ADAPTER.dump_python(config.auth, mode="python"))
    return cast(dict, payload)


def merge_masked_auth_secrets(
    current: ServerAuthProviderConfig,
    updated: ServerAuthProviderConfig,
) -> ServerAuthProviderConfig:
    """Replace secret-mask sentinels with values from the current provider."""

    current_data = AUTH_PROVIDER_ADAPTER.dump_python(current, mode="python")
    updated_data = AUTH_PROVIDER_ADAPTER.dump_python(updated, mode="python")
    if current.provider != updated.provider and _contains_secret_mask(updated_data):
        raise TypeError(
            "Masked secrets can only preserve credentials from the same provider."
        )
    merged = _merge_masked_values(current_data, updated_data)
    return AUTH_PROVIDER_ADAPTER.validate_python(_jsonable(merged))


def _contains_secret_mask(value: object) -> bool:
    if isinstance(value, SecretStr):
        return value.get_secret_value() == SECRET_MASK
    if isinstance(value, dict):
        return any(_contains_secret_mask(item) for item in value.values())
    if isinstance(value, list):
        return any(_contains_secret_mask(item) for item in value)
    return False


def _merge_masked_values(current: object, updated: object) -> object:
    if isinstance(updated, SecretStr):
        if updated.get_secret_value() != SECRET_MASK:
            return updated
        if not isinstance(current, SecretStr):
            raise TypeError(
                "Masked secrets can only preserve credentials from the same provider."
            )
        return current
    if isinstance(updated, dict):
        current_items = current if isinstance(current, dict) else {}
        return {
            key: _merge_masked_values(current_items.get(key), value)
            for key, value in updated.items()
        }
    if isinstance(updated, list):
        current_items = current if isinstance(current, list) else []
        return [
            _merge_masked_values(
                current_items[index] if index < len(current_items) else None,
                value,
            )
            for index, value in enumerate(updated)
        ]
    return updated


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
