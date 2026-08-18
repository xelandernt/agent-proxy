from __future__ import annotations

import re
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from proxy.servers.constants import NAME_PATTERN

MODEL_NAME_RE = re.compile(NAME_PATTERN)


class ApiKeyCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=100)
    models: list[str] = Field(min_length=1)

    @field_validator("models")
    @classmethod
    def validate_models(cls, value: list[str]) -> list[str]:
        return _validate_models(value)


class ApiKeyUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, min_length=1, max_length=100)
    models: list[str] | None = Field(default=None, min_length=1)

    @field_validator("models")
    @classmethod
    def validate_models(cls, value: list[str] | None) -> list[str] | None:
        return _validate_models(value) if value is not None else None


class ApiKeyView(BaseModel):
    id: UUID
    name: str
    prefix: str
    models: list[str]
    created_at: datetime
    last_used_at: datetime | None
    revoked_at: datetime | None


class ApiKeyCreated(ApiKeyView):
    key: str


class AuthenticatedApiKey(BaseModel):
    """Internal authorization context for `/v1` requests."""

    id: UUID
    user_id: UUID
    models: frozenset[str]


def _validate_models(value: list[str]) -> list[str]:
    if len(value) != len(set(value)):
        raise ValueError("models must not contain duplicates.")
    if any(MODEL_NAME_RE.fullmatch(name) is None for name in value):
        raise ValueError("models contains an invalid model name.")
    return value
