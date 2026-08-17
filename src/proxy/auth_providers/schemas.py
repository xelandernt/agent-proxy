from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from proxy.auth_providers.models import (
    AuthProviderDefinition,
    config_to_public_auth_payload,
)
from proxy.providers import ManagedAuthProviderConfig
from proxy.servers.constants import NAME_PATTERN


class AuthProviderCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(pattern=NAME_PATTERN, max_length=100)
    auth: ManagedAuthProviderConfig


class AuthProviderUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    auth: ManagedAuthProviderConfig


class AuthProviderView(BaseModel):
    """Admin representation with credential fields omitted."""

    name: str
    auth: dict[str, object]


def to_view(definition: AuthProviderDefinition) -> AuthProviderView:
    return AuthProviderView(
        name=definition.name,
        auth=config_to_public_auth_payload(definition.auth),
    )
