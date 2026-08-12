from __future__ import annotations

from pydantic import AnyHttpUrl, BaseModel, ConfigDict, Field

from proxy.providers import ServerAuthProviderConfig
from proxy.servers.models import NAME_PATTERN


class ServerCreateRequest(BaseModel):
    """Payload for creating a server."""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(pattern=NAME_PATTERN, max_length=100)
    description: str = Field(default="", max_length=255)
    upstream_url: AnyHttpUrl = Field(max_length=2048)
    auth: ServerAuthProviderConfig
    verify_upstream_tls: bool = True
    forward_client_credentials: bool = False


class ServerUpdateRequest(BaseModel):
    """Payload for updating a server; the name is immutable."""

    model_config = ConfigDict(extra="forbid")

    description: str = Field(default="", max_length=255)
    upstream_url: AnyHttpUrl = Field(max_length=2048)
    auth: ServerAuthProviderConfig
    verify_upstream_tls: bool = True
    forward_client_credentials: bool = False


class ServerView(BaseModel):
    """Admin-facing server representation with secrets masked."""

    name: str
    description: str
    upstream_url: str
    auth: ServerAuthProviderConfig
    verify_upstream_tls: bool
    forward_client_credentials: bool
