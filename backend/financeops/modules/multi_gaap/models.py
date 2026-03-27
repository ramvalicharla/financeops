from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, ForeignKey, Index, Numeric, String, UniqueConstraint, event, select, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from financeops.db.base import Base
from financeops.platform.db.models.entities import CpEntity


class MultiGAAPConfig(Base):
    __tablename__ = "multi_gaap_configs"
    __table_args__ = (
        UniqueConstraint("tenant_id", "entity_id", name="uq_multi_gaap_configs_tenant_entity"),
        Index("idx_multi_gaap_configs_tenant_entity", "tenant_id", "entity_id"),
        {"extend_existing": True},
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, nullable=False, server_default=text("gen_random_uuid()"))
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    entity_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("cp_entities.id", ondelete="RESTRICT"),
        nullable=False,
    )
    primary_gaap: Mapped[str] = mapped_column(String(20), nullable=False, server_default=text("'INDAS'"), default="INDAS")
    secondary_gaaps: Mapped[list[str]] = mapped_column(JSONB, nullable=False, server_default=text("'[]'::jsonb"), default=list)
    revenue_recognition_policy: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default=text("'{}'::jsonb"), default=dict)
    lease_classification_policy: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default=text("'{}'::jsonb"), default=dict)
    financial_instruments_policy: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default=text("'{}'::jsonb"), default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text("now()"))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text("now()"))


class MultiGAAPRun(Base):
    __tablename__ = "multi_gaap_runs"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "entity_id",
            "period",
            "gaap_framework",
            name="uq_multi_gaap_runs_tenant_entity_period_framework",
        ),
        Index(
            "idx_multi_gaap_runs_tenant_entity_period_framework",
            "tenant_id",
            "entity_id",
            "period",
            "gaap_framework",
        ),
        {"extend_existing": True},
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, nullable=False, server_default=text("gen_random_uuid()"))
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    entity_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("cp_entities.id", ondelete="RESTRICT"),
        nullable=False,
    )
    period: Mapped[str] = mapped_column(String(7), nullable=False)
    gaap_framework: Mapped[str] = mapped_column(String(20), nullable=False)
    revenue: Mapped[Decimal] = mapped_column(Numeric(20, 2), nullable=False)
    gross_profit: Mapped[Decimal] = mapped_column(Numeric(20, 2), nullable=False)
    ebitda: Mapped[Decimal] = mapped_column(Numeric(20, 2), nullable=False)
    ebit: Mapped[Decimal] = mapped_column(Numeric(20, 2), nullable=False)
    profit_before_tax: Mapped[Decimal] = mapped_column(Numeric(20, 2), nullable=False)
    profit_after_tax: Mapped[Decimal] = mapped_column(Numeric(20, 2), nullable=False)
    total_assets: Mapped[Decimal] = mapped_column(Numeric(20, 2), nullable=False)
    total_equity: Mapped[Decimal] = mapped_column(Numeric(20, 2), nullable=False)
    adjustments: Mapped[list[dict]] = mapped_column(JSONB, nullable=False, server_default=text("'[]'::jsonb"), default=list)
    created_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text("now()"))


def _resolve_entity_id_from_tenant(connection, tenant_id: uuid.UUID | None) -> uuid.UUID | None:
    if tenant_id is None:
        return None
    entity_id = connection.execute(
        select(CpEntity.id)
        .where(
            CpEntity.tenant_id == tenant_id,
            CpEntity.status == "active",
        )
        .order_by(CpEntity.created_at.asc(), CpEntity.id.asc())
        .limit(1)
    ).scalar_one_or_none()
    if entity_id is not None:
        return entity_id
    return connection.execute(
        select(CpEntity.id)
        .where(CpEntity.status == "active")
        .order_by(CpEntity.created_at.asc(), CpEntity.id.asc())
        .limit(1)
    ).scalar_one_or_none()


@event.listens_for(MultiGAAPConfig, "before_insert")
def _set_multi_gaap_config_entity_id(mapper, connection, target: MultiGAAPConfig) -> None:
    del mapper
    if target.entity_id is not None:
        return
    resolved = _resolve_entity_id_from_tenant(connection, target.tenant_id)
    if resolved is not None:
        target.entity_id = resolved


@event.listens_for(MultiGAAPRun, "before_insert")
def _set_multi_gaap_run_entity_id(mapper, connection, target: MultiGAAPRun) -> None:
    del mapper
    if target.entity_id is not None:
        return
    resolved = _resolve_entity_id_from_tenant(connection, target.tenant_id)
    if resolved is not None:
        target.entity_id = resolved


__all__ = ["MultiGAAPConfig", "MultiGAAPRun"]
