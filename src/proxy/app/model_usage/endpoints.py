from __future__ import annotations

from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status

from proxy.app.dependencies import CurrentUserDep, ModelUsageServiceDep
from proxy.app.model_usage.schemas import ModelUsageSeriesReport, UserModelUsageReport
from proxy.app.model_usage.service import (
    InvalidModelUsageRange,
    ModelUsageApiKeyNotFound,
)
from proxy.app.usage.types import UsageBucket
from proxy.servers.constants import NAME_PATTERN

router = APIRouter(prefix="/api/user/usage", tags=["user-model-usage"])

FromQuery = Annotated[datetime, Query(alias="from")]
ModelQuery = Annotated[
    str | None, Query(min_length=1, max_length=100, pattern=NAME_PATTERN)
]


@router.get("", response_model=UserModelUsageReport)
async def user_model_usage(
    user: CurrentUserDep,
    service: ModelUsageServiceDep,
    from_: FromQuery,
    to: datetime,
    model: ModelQuery = None,
    api_key_id: UUID | None = None,
) -> UserModelUsageReport:
    try:
        return await service.user_report(
            user.id,
            from_,
            to,
            model=model,
            api_key_id=api_key_id,
        )
    except (InvalidModelUsageRange, ModelUsageApiKeyNotFound) as error:
        raise _invalid_report(error) from error


@router.get("/series", response_model=ModelUsageSeriesReport)
async def user_model_usage_series(
    user: CurrentUserDep,
    service: ModelUsageServiceDep,
    from_: FromQuery,
    to: datetime,
    bucket: UsageBucket,
    model: ModelQuery = None,
    api_key_id: UUID | None = None,
) -> ModelUsageSeriesReport:
    try:
        return await service.user_series(
            user.id,
            from_,
            to,
            bucket,
            model=model,
            api_key_id=api_key_id,
        )
    except (InvalidModelUsageRange, ModelUsageApiKeyNotFound) as error:
        raise _invalid_report(error) from error


def _invalid_report(error: Exception) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        detail=error.args[0] if error.args else str(error),
    )
