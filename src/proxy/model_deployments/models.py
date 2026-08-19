from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from proxy.database import Base


class ModelDeploymentRecord(Base):
    """A public model alias linked to a reusable inference provider."""

    __tablename__ = "model_deployments"

    name: Mapped[str] = mapped_column(String(100), primary_key=True)
    provider: Mapped[str] = mapped_column(
        ForeignKey("model_providers.name", ondelete="RESTRICT"), index=True
    )
    model_id: Mapped[str] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
