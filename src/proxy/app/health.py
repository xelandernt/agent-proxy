from __future__ import annotations

from typing import Literal

from fastapi import APIRouter
from pydantic import BaseModel


class HealthResponse(BaseModel):
    """Successful gateway health-check response."""

    status: Literal["ok"]


router = APIRouter()


@router.get("/healthz", response_model=HealthResponse)
def healthz() -> HealthResponse:
    """Report that the gateway process is running."""

    return HealthResponse(status="ok")
