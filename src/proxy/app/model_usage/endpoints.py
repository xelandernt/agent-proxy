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

router = APIRouter(prefix="/api/user/usage", tags=["user-model-usage"])

FromQuery = Annotated[datetime, Query(alias="from")]
ModelQuery = Annotated[list[str] | None, Query()]


@router.get("", response_model=UserModelUsageReport)
async def user_model_usage(
    user: CurrentUserDep,
    service: ModelUsageServiceDep,
    from_: FromQuery,
    to: datetime,
    models: ModelQuery = None,
    api_key_ids: Annotated[list[str] | None, Query()] = None,
) -> UserModelUsageReport:
    try:
        return await service.user_report(
            user.id,
            from_,
            to,
            models=_query_values(models),
            api_key_ids=_uuid_values(api_key_ids),
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
    models: ModelQuery = None,
    api_key_ids: Annotated[list[str] | None, Query()] = None,
) -> ModelUsageSeriesReport:
    try:
        return await service.user_series(
            user.id,
            from_,
            to,
            bucket,
            models=_query_values(models),
            api_key_ids=_uuid_values(api_key_ids),
        )
    except (InvalidModelUsageRange, ModelUsageApiKeyNotFound) as error:
        raise _invalid_report(error) from error


def _invalid_report(error: Exception) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        detail=error.args[0] if error.args else str(error),
    )


def _query_values(values: list[str] | None) -> list[str] | None:
    expanded = [item for value in values or [] for item in value.split(",") if item]
    return expanded or None


def _uuid_values(values: list[str] | None) -> list[UUID] | None:
    try:
        parsed = [UUID(value) for value in _query_values(values) or []]
    except ValueError as error:
        raise _invalid_report(error) from error
    return parsed or None
