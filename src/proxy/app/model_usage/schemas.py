from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel

from proxy.app.usage.types import UsageBucket


class ModelUsageAggregate(BaseModel):
    requests: int
    successful_requests: int
    failed_requests: int
    metered_requests: int
    input_tokens: int | None
    output_tokens: int | None
    total_tokens: int | None
    cached_metered_requests: int
    cached_tokens: int | None
    costed_requests: int
    cost_usd: str | None


class ModelUsageModelBreakdown(ModelUsageAggregate):
    model: str


class ModelUsageApiKeyBreakdown(ModelUsageAggregate):
    api_key_id: UUID
    name: str
    prefix: str
    revoked: bool


class ModelUsageUserBreakdown(ModelUsageAggregate):
    user_id: UUID
    display_name: str | None
    email: str


class UserModelUsageReport(ModelUsageAggregate):
    start: datetime
    end: datetime
    models: list[ModelUsageModelBreakdown]
    api_keys: list[ModelUsageApiKeyBreakdown]


class AdminModelUsageReport(UserModelUsageReport):
    users: list[ModelUsageUserBreakdown]


class ModelUsageSeriesPoint(ModelUsageAggregate):
    ts: datetime


class ModelUsageSeriesReport(BaseModel):
    start: datetime
    end: datetime
    bucket: UsageBucket
    points: list[ModelUsageSeriesPoint]
