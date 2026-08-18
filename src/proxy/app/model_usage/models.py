from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    ForeignKey,
    Identity,
    Integer,
    String,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from proxy.database import Base


class ModelUsageEvent(Base):
    __tablename__ = "model_usage_events"

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), index=True
    )
    api_key_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("api_keys.id", ondelete="RESTRICT"), index=True
    )
    model_name: Mapped[str] = mapped_column(String(100), index=True)
    provider: Mapped[str | None] = mapped_column(String(64), nullable=True)
    status_code: Mapped[int] = mapped_column(Integer)
    input_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    output_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    total_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    duration_ms: Mapped[int] = mapped_column(Integer)
    error_type: Mapped[str | None] = mapped_column(String(128), nullable=True)
    streaming: Mapped[bool] = mapped_column(Boolean)
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
