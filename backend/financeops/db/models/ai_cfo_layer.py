from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, ForeignKey, Index, Numeric, String, Text, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from financeops.db.base import Base


class AiCfoAnomaly(Base):
    __tablename__ = "analytics_anomalies"
    __table_args__ = (
        Index("ix_analytics_anomalies_tenant_metric", "tenant_id", "metric_name"),
        Index("ix_analytics_anomalies_tenant_created", "tenant_id", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("iam_tenants.id", ondelete="CASCADE"),
        nullable=False,
    )
    org_entity_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("cp_entities.id", ondelete="SET NULL"),
        nullable=True,
    )
    org_group_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("cp_groups.id", ondelete="SET NULL"),
        nullable=True,
    )
    metric_name: Mapped[str] = mapped_column(String(64), nullable=False)
    anomaly_type: Mapped[str] = mapped_column(String(64), nullable=False)
    deviation_value: Mapped[Decimal] = mapped_column(Numeric(24, 6), nullable=False)
    severity: Mapped[str] = mapped_column(String(16), nullable=False)
    fact_json: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False, default=dict)
    lineage_json: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False, default=dict)
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("iam_users.id", ondelete="SET NULL"),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("now()"),
    )


class AiCfoRecommendation(Base):
    __tablename__ = "analytics_recommendations"
    __table_args__ = (
        Index(
            "ix_analytics_recommendations_tenant_type",
            "tenant_id",
            "recommendation_type",
        ),
        Index("ix_analytics_recommendations_tenant_created", "tenant_id", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("iam_tenants.id", ondelete="CASCADE"),
        nullable=False,
    )
    org_entity_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("cp_entities.id", ondelete="SET NULL"),
        nullable=True,
    )
    org_group_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("cp_groups.id", ondelete="SET NULL"),
        nullable=True,
    )
    recommendation_type: Mapped[str] = mapped_column(String(64), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    severity: Mapped[str] = mapped_column(String(16), nullable=False)
    evidence_json: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False, default=dict)
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("iam_users.id", ondelete="SET NULL"),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("now()"),
    )


__all__ = [
    "AiCfoAnomaly",
    "AiCfoRecommendation",
]

