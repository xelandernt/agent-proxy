from __future__ import annotations

from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status

from proxy.app.admin.auth import require_admin
from proxy.app.dependencies import ModelUsageServiceDep
from proxy.app.model_usage.schemas import AdminModelUsageReport, ModelUsageSeriesReport
from proxy.app.model_usage.service import InvalidModelUsageRange
from proxy.app.usage.types import UsageBucket
from proxy.servers.constants import NAME_PATTERN

router = APIRouter(
    prefix="/api/admin/usage",
    tags=["admin-model-usage"],
    dependencies=[Depends(require_admin)],
)

FromQuery = Annotated[datetime, Query(alias="from")]
ModelQuery = Annotated[
    str | None, Query(min_length=1, max_length=100, pattern=NAME_PATTERN)
]


@router.get("", response_model=AdminModelUsageReport)
async def admin_model_usage(
    service: ModelUsageServiceDep,
    from_: FromQuery,
    to: datetime,
    user_id: UUID | None = None,
    model: ModelQuery = None,
    api_key_id: UUID | None = None,
) -> AdminModelUsageReport:
    try:
        return await service.admin_report(
            from_,
            to,
            user_id=user_id,
            model=model,
            api_key_id=api_key_id,
        )
    except InvalidModelUsageRange as error:
        raise _invalid_report(error) from error


@router.get("/series", response_model=ModelUsageSeriesReport)
async def admin_model_usage_series(
    service: ModelUsageServiceDep,
    from_: FromQuery,
    to: datetime,
    bucket: UsageBucket,
    user_id: UUID | None = None,
    model: ModelQuery = None,
    api_key_id: UUID | None = None,
) -> ModelUsageSeriesReport:
    try:
        return await service.admin_series(
            from_,
            to,
            bucket,
            user_id=user_id,
            model=model,
            api_key_id=api_key_id,
        )
    except InvalidModelUsageRange as error:
        raise _invalid_report(error) from error


def _invalid_report(error: InvalidModelUsageRange) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        detail=str(error),
    )
