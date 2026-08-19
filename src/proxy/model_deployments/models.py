from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Numeric, String
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
    input_usd_per_million_tokens: Mapped[Decimal | None] = mapped_column(
        Numeric(20, 12), nullable=True
    )
    cached_input_usd_per_million_tokens: Mapped[Decimal | None] = mapped_column(
        Numeric(20, 12), nullable=True
    )
    output_usd_per_million_tokens: Mapped[Decimal | None] = mapped_column(
        Numeric(20, 12), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        CheckConstraint(
            "(input_usd_per_million_tokens IS NULL AND "
            "cached_input_usd_per_million_tokens IS NULL AND "
            "output_usd_per_million_tokens IS NULL) OR "
            "(input_usd_per_million_tokens IS NOT NULL AND "
            "cached_input_usd_per_million_tokens IS NOT NULL AND "
            "output_usd_per_million_tokens IS NOT NULL)",
            name="ck_model_deployments_pricing_atomic",
        ),
        CheckConstraint(
            "input_usd_per_million_tokens >= 0",
            name="ck_model_deployments_input_price_nonnegative",
        ),
        CheckConstraint(
            "cached_input_usd_per_million_tokens >= 0",
            name="ck_model_deployments_cached_input_price_nonnegative",
        ),
        CheckConstraint(
            "output_usd_per_million_tokens >= 0",
            name="ck_model_deployments_output_price_nonnegative",
        ),
    )
