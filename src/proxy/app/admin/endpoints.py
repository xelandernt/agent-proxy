from __future__ import annotations

from fastapi import APIRouter, Depends

from proxy.app.admin.auth import require_admin

router = APIRouter(
    prefix="/api/admin",
    tags=["admin"],
    dependencies=[Depends(require_admin)],
)


@router.get("/me")
def me() -> dict[str, bool]:
    """Report whether the caller holds a valid admin token."""

    return {"authenticated": True}
