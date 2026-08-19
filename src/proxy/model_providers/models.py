from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from proxy.database import Base


class ModelProviderRecord(Base):
    __tablename__ = "model_providers"

    name: Mapped[str] = mapped_column(String(100), primary_key=True)
    config: Mapped[dict[str, object]] = mapped_column(JSONB)
    encrypted_credentials: Mapped[str] = mapped_column(Text)
    credential_names: Mapped[list[str]] = mapped_column(JSONB, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
