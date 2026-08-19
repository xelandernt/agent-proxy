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

router = APIRouter(
    prefix="/api/admin/usage",
    tags=["admin-model-usage"],
    dependencies=[Depends(require_admin)],
)

FromQuery = Annotated[datetime, Query(alias="from")]
ModelQuery = Annotated[list[str] | None, Query()]


@router.get("", response_model=AdminModelUsageReport)
async def admin_model_usage(
    service: ModelUsageServiceDep,
    from_: FromQuery,
    to: datetime,
    user_id: UUID | None = None,
    models: ModelQuery = None,
    api_key_ids: Annotated[list[str] | None, Query()] = None,
) -> AdminModelUsageReport:
    try:
        return await service.admin_report(
            from_,
            to,
            user_id=user_id,
            models=_query_values(models),
            api_key_ids=_uuid_values(api_key_ids),
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
    models: ModelQuery = None,
    api_key_ids: Annotated[list[str] | None, Query()] = None,
) -> ModelUsageSeriesReport:
    try:
        return await service.admin_series(
            from_,
            to,
            bucket,
            user_id=user_id,
            models=_query_values(models),
            api_key_ids=_uuid_values(api_key_ids),
        )
    except InvalidModelUsageRange as error:
        raise _invalid_report(error) from error


def _invalid_report(error: InvalidModelUsageRange) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        detail=str(error),
    )


def _query_values(values: list[str] | None) -> list[str] | None:
    expanded = [item for value in values or [] for item in value.split(",") if item]
    return expanded or None


def _uuid_values(values: list[str] | None) -> list[UUID] | None:
    try:
        parsed = [UUID(value) for value in _query_values(values) or []]
    except ValueError as error:
        raise _invalid_report(InvalidModelUsageRange(str(error))) from error
    return parsed or None
