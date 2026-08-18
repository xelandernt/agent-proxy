from __future__ import annotations

import re
from collections.abc import Mapping
from datetime import datetime

from pydantic import (
    AnyHttpUrl,
    BaseModel,
    ConfigDict,
    Field,
    JsonValue,
    SecretStr,
    field_validator,
    model_validator,
)

from proxy.servers.constants import NAME_PATTERN

RESERVED_PROVIDER_SETTINGS = frozenset(
    {
        "api_base",
        "api_key",
        "background",
        "input",
        "instructions",
        "metadata",
        "model",
        "previous_response_id",
        "reasoning",
        "store",
        "stream",
        "tool_choice",
        "tools",
        "user",
    }
)
SECRET_NAME_PATTERN = re.compile(
    r"(?:^|_)(?:api_?key|access_?key|private_?key|password|secret|token|credential|authorization)(?:$|_)",
    re.IGNORECASE,
)


class ModelDeploymentCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(pattern=NAME_PATTERN, max_length=100)
    description: str = Field(default="", max_length=255)
    upstream_model: str = Field(min_length=1, max_length=255)
    api_base: AnyHttpUrl | None = Field(default=None, max_length=2048)
    settings: dict[str, JsonValue] = Field(default_factory=dict)
    secrets: dict[str, SecretStr] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_provider_arguments(self) -> ModelDeploymentCreate:
        _validate_argument_names(self.settings, self.secrets)
        return self


class ModelDeploymentUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    description: str | None = Field(default=None, max_length=255)
    upstream_model: str | None = Field(default=None, min_length=1, max_length=255)
    api_base: AnyHttpUrl | None = Field(default=None, max_length=2048)
    settings: dict[str, JsonValue] | None = None
    set_secrets: dict[str, SecretStr] = Field(default_factory=dict)
    remove_secrets: list[str] = Field(default_factory=list)

    @field_validator("remove_secrets")
    @classmethod
    def unique_removed_secrets(cls, value: list[str]) -> list[str]:
        if len(value) != len(set(value)):
            raise ValueError("remove_secrets must not contain duplicates.")
        return value

    @model_validator(mode="after")
    def validate_provider_arguments(self) -> ModelDeploymentUpdate:
        _validate_argument_names(self.settings or {}, self.set_secrets)
        overlap = set(self.set_secrets) & set(self.remove_secrets)
        if overlap:
            raise ValueError(
                "A secret cannot be set and removed in the same request: "
                + ", ".join(sorted(overlap))
            )
        return self


class ModelDeploymentView(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    name: str
    description: str
    upstream_model: str
    api_base: str | None
    settings: dict[str, JsonValue]
    secret_names: list[str]
    created_at: datetime
    updated_at: datetime


class ResolvedModelDeployment(BaseModel):
    """Internal server-owned LiteLLM connection configuration."""

    model_config = ConfigDict(extra="forbid")

    name: str
    upstream_model: str
    api_base: str | None
    settings: dict[str, JsonValue]
    secrets: dict[str, str]


def _validate_argument_names(
    settings: Mapping[str, object],
    secrets: Mapping[str, object],
) -> None:
    overlap = set(settings) & set(secrets)
    if overlap:
        raise ValueError(
            "Provider arguments cannot be both settings and secrets: "
            + ", ".join(sorted(overlap))
        )
    reserved = set(settings) & RESERVED_PROVIDER_SETTINGS
    reserved.update(set(secrets) & (RESERVED_PROVIDER_SETTINGS - {"api_key"}))
    if reserved:
        raise ValueError(
            "Provider arguments are reserved by the gateway: "
            + ", ".join(sorted(reserved))
        )
    misplaced = [name for name in settings if SECRET_NAME_PATTERN.search(name)]
    if misplaced:
        raise ValueError(
            "Credential-like provider arguments belong in secrets: "
            + ", ".join(sorted(misplaced))
        )
    invalid = [name for name in set(settings) | set(secrets) if not name.isidentifier()]
    if invalid:
        raise ValueError(
            "Provider argument names must be valid Python identifiers: "
            + ", ".join(sorted(invalid))
        )
