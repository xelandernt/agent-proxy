from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from proxy.database import Base


class ApiKeyRecord(Base):
    __tablename__ = "api_keys"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), index=True
    )
    name: Mapped[str] = mapped_column(String(100))
    prefix: Mapped[str] = mapped_column(String(16), unique=True)
    digest: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    last_used_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    revoked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class ApiKeyModelRecord(Base):
    __tablename__ = "api_key_models"

    api_key_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("api_keys.id", ondelete="CASCADE"),
        primary_key=True,
    )
    model_name: Mapped[str] = mapped_column(
        String(100),
        ForeignKey("model_deployments.name", ondelete="RESTRICT"),
        primary_key=True,
    )

    __table_args__ = (
        UniqueConstraint("api_key_id", "model_name", name="uq_api_key_model"),
    )
