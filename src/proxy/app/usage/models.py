from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, DateTime, Identity, Index, String
from sqlalchemy.orm import Mapped, mapped_column

from proxy.database import Base


class UsageEvent(Base):
    """One MCP JSON-RPC request proxied by the gateway."""

    __tablename__ = "usage_events"

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    server_name: Mapped[str] = mapped_column(String(100))
    method: Mapped[str] = mapped_column(String(64))
    item: Mapped[str | None] = mapped_column(String(255))
    client_app: Mapped[str | None] = mapped_column(String(128))
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        Index("ix_usage_events_server_ts", "server_name", "ts"),
        Index("ix_usage_events_server_method_ts", "server_name", "method", "ts"),
    )
