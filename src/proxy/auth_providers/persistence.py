from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, DateTime, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from proxy.database import Base


class AuthProviderRecord(Base):
    """SQLAlchemy row for a reusable authentication provider."""

    __tablename__ = "auth_providers"

    name: Mapped[str] = mapped_column(String(100), primary_key=True)
    auth: Mapped[dict] = mapped_column(JSON().with_variant(JSONB, "postgresql"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
