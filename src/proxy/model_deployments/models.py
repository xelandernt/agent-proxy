from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from proxy.database import Base


class ModelDeploymentRecord(Base):
    """Encrypted upstream configuration behind a public model alias."""

    __tablename__ = "model_deployments"

    name: Mapped[str] = mapped_column(String(100), primary_key=True)
    description: Mapped[str] = mapped_column(String(255), default="")
    upstream_model: Mapped[str] = mapped_column(String(255))
    api_base: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    settings: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    encrypted_secrets: Mapped[str] = mapped_column(Text)
    secret_names: Mapped[list[str]] = mapped_column(JSONB, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
