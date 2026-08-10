from __future__ import annotations

from pydantic import AnyHttpUrl, BaseModel, ConfigDict, Field

from proxy.providers import AuthProviderConfig
from proxy.servers.models import NAME_PATTERN


class ServerCreateRequest(BaseModel):
    """Payload for creating a server."""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(pattern=NAME_PATTERN)
    description: str = ""
    upstream_url: AnyHttpUrl
    auth: AuthProviderConfig
    verify_upstream_tls: bool = True


class ServerUpdateRequest(BaseModel):
    """Payload for updating a server; the name is immutable."""

    model_config = ConfigDict(extra="forbid")

    description: str = ""
    upstream_url: AnyHttpUrl
    auth: AuthProviderConfig
    verify_upstream_tls: bool = True


class ServerView(BaseModel):
    """Admin-facing server representation with secrets masked."""

    name: str
    description: str
    upstream_url: str
    auth: AuthProviderConfig
    verify_upstream_tls: bool
