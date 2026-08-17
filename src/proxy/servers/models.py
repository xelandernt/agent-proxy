from __future__ import annotations

from datetime import datetime

from pydantic import (
    AnyHttpUrl,
    BaseModel,
    ConfigDict,
    Field,
    model_validator,
)
from sqlalchemy import Boolean, DateTime, ForeignKey, String, text
from sqlalchemy.orm import Mapped, mapped_column

from proxy.database import Base
from proxy.servers.constants import NAME_PATTERN


class McpServerConfig(BaseModel):
    """One protected modern MCP endpoint and its unauthenticated backend."""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(pattern=NAME_PATTERN, max_length=100)
    description: str = Field(default="", max_length=255)
    upstream_url: AnyHttpUrl = Field(max_length=2048)
    auth_provider: str | None = Field(
        default=None,
        pattern=NAME_PATTERN,
        max_length=100,
    )
    verify_upstream_tls: bool = True
    forward_client_credentials: bool = False

    @model_validator(mode="after")
    def validate_forward_client_credentials(self) -> McpServerConfig:
        if self.forward_client_credentials and self.auth_provider is not None:
            raise ValueError(
                "forward_client_credentials requires no auth provider: "
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
    auth_provider: Mapped[str | None] = mapped_column(
        String(100),
        ForeignKey("auth_providers.name", ondelete="RESTRICT"),
        nullable=True,
        index=True,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    def to_config(self) -> McpServerConfig:
        """Convert the row to a validated runtime config."""

        return McpServerConfig(
            name=self.name,
            description=self.description,
            upstream_url=self.upstream_url,
            verify_upstream_tls=self.verify_upstream_tls,
            forward_client_credentials=self.forward_client_credentials,
            auth_provider=self.auth_provider,
        )
