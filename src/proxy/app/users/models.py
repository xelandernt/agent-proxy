from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Index, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from proxy.database import Base


class UserRecord(Base):
    """Durable user keyed by the identity provider's stable subject."""

    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    issuer: Mapped[str] = mapped_column(String(2048))
    subject: Mapped[str] = mapped_column(String(255))
    email: Mapped[str] = mapped_column(String(320), index=True)
    email_verified: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    display_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    last_login_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        UniqueConstraint("issuer", "subject", name="uq_users_issuer_subject"),
        Index("ix_users_last_login_at", "last_login_at"),
    )
