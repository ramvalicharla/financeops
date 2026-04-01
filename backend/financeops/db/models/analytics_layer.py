from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Date, DateTime, ForeignKey, Index, Numeric, String, Text, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from financeops.db.base import Base


class AnalyticsSnapshot(Base):
    __tablename__ = "analytics_snapshots"
    __table_args__ = (
        Index("ix_analytics_snapshots_tenant", "tenant_id"),
        Index("ix_analytics_snapshots_entity", "tenant_id", "org_entity_id"),
        Index("ix_analytics_snapshots_group", "tenant_id", "org_group_id"),
        Index("ix_analytics_snapshots_type_date", "tenant_id", "snapshot_type", "as_of_date"),
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
    snapshot_type: Mapped[str] = mapped_column(String(16), nullable=False)
    as_of_date: Mapped[date] = mapped_column(Date, nullable=False)
    period_from: Mapped[date | None] = mapped_column(Date, nullable=True)
    period_to: Mapped[date | None] = mapped_column(Date, nullable=True)
    data_json: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("now()"),
    )


class AnalyticsMetric(Base):
    __tablename__ = "analytics_metrics"
    __table_args__ = (
        Index("ix_analytics_metrics_tenant_metric", "tenant_id", "metric_name"),
        Index("ix_analytics_metrics_tenant_created", "tenant_id", "created_at"),
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
    metric_name: Mapped[str] = mapped_column(String(64), nullable=False)
    metric_value: Mapped[Decimal] = mapped_column(Numeric(24, 6), nullable=False)
    dimension_json: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("now()"),
    )


class AnalyticsVariance(Base):
    __tablename__ = "analytics_variances"
    __table_args__ = (
        Index("ix_analytics_variances_tenant_metric", "tenant_id", "metric_name"),
        Index("ix_analytics_variances_tenant_created", "tenant_id", "created_at"),
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
    metric_name: Mapped[str] = mapped_column(String(64), nullable=False)
    current_value: Mapped[Decimal] = mapped_column(Numeric(24, 6), nullable=False)
    previous_value: Mapped[Decimal] = mapped_column(Numeric(24, 6), nullable=False)
    variance_value: Mapped[Decimal] = mapped_column(Numeric(24, 6), nullable=False)
    variance_percent: Mapped[Decimal | None] = mapped_column(Numeric(24, 6), nullable=True)
    dimension_json: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("now()"),
    )


class Budget(Base):
    __tablename__ = "budgets"
    __table_args__ = (
        Index("ix_budgets_tenant_entity_period", "tenant_id", "org_entity_id", "period"),
        Index("ix_budgets_tenant_account", "tenant_id", "account_id"),
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
    org_entity_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("cp_entities.id", ondelete="CASCADE"),
        nullable=False,
    )
    period: Mapped[str] = mapped_column(String(7), nullable=False)  # YYYY-MM
    account_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tenant_coa_accounts.id", ondelete="RESTRICT"),
        nullable=False,
    )
    budget_amount: Mapped[Decimal] = mapped_column(Numeric(24, 6), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("now()"),
    )


class AnalyticsAlert(Base):
    __tablename__ = "analytics_alerts"
    __table_args__ = (
        Index("ix_analytics_alerts_tenant_metric", "tenant_id", "metric_name"),
        Index("ix_analytics_alerts_tenant_created", "tenant_id", "created_at"),
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
    metric_name: Mapped[str] = mapped_column(String(64), nullable=False)
    threshold: Mapped[Decimal] = mapped_column(Numeric(24, 6), nullable=False)
    condition: Mapped[str] = mapped_column(String(16), nullable=False)  # GT/LT/ABS_GT
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("now()"),
    )


__all__ = [
    "AnalyticsAlert",
    "AnalyticsMetric",
    "AnalyticsSnapshot",
    "AnalyticsVariance",
    "Budget",
]
