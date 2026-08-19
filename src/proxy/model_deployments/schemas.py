from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from proxy.servers.constants import NAME_PATTERN


class ModelDeploymentCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(pattern=NAME_PATTERN, max_length=100)
    provider: str = Field(pattern=NAME_PATTERN, max_length=100)
    model_id: str = Field(min_length=1, max_length=255)


class ModelDeploymentUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    provider: str | None = Field(default=None, pattern=NAME_PATTERN, max_length=100)
    model_id: str | None = Field(default=None, min_length=1, max_length=255)


class ModelDeploymentView(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    name: str
    provider: str
    model_id: str
    created_at: datetime
    updated_at: datetime


class ResolvedModelDeployment(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    upstream_model: str
    api_base: str | None
    settings: dict[str, Any]
    secrets: dict[str, str]
