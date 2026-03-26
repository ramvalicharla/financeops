from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from financeops.db.base import Base


class FaAssetClass(Base):
    __tablename__ = "fa_asset_classes"
    __table_args__ = (
        Index("idx_fa_asset_classes_tenant_id", "tenant_id"),
        Index("idx_fa_asset_classes_entity_id", "entity_id"),
        Index("idx_fa_asset_classes_name", "name"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        nullable=False,
        server_default=text("gen_random_uuid()"),
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("iam_tenants.id", ondelete="CASCADE"),
        nullable=False,
    )
    entity_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("cp_entities.id", ondelete="CASCADE"),
        nullable=False,
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    asset_type: Mapped[str] = mapped_column(String(20), nullable=False)
    default_method: Mapped[str] = mapped_column(String(20), nullable=False)
    default_useful_life_years: Mapped[int | None] = mapped_column(Integer, nullable=True)
    default_residual_pct: Mapped[Decimal | None] = mapped_column(Numeric(5, 4), nullable=True)
    it_act_block_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    it_act_depreciation_rate: Mapped[Decimal | None] = mapped_column(Numeric(5, 4), nullable=True)
    coa_asset_account_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tenant_coa_accounts.id", ondelete="SET NULL"),
        nullable=True,
    )
    coa_accum_dep_account_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tenant_coa_accounts.id", ondelete="SET NULL"),
        nullable=True,
    )
    coa_dep_expense_account_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tenant_coa_accounts.id", ondelete="SET NULL"),
        nullable=True,
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"), default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        server_default=func.now(),
        onupdate=func.now(),
    )


class FaAsset(Base):
    __tablename__ = "fa_assets"
    __table_args__ = (
        UniqueConstraint("tenant_id", "entity_id", "asset_code", name="uq_fa_assets_tenant_entity_code"),
        Index("idx_fa_assets_tenant_id", "tenant_id"),
        Index("idx_fa_assets_entity_id", "entity_id"),
        Index("idx_fa_assets_asset_class_id", "asset_class_id"),
        Index("idx_fa_assets_status", "status"),
        Index("idx_fa_assets_asset_code", "asset_code"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        nullable=False,
        server_default=text("gen_random_uuid()"),
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("iam_tenants.id", ondelete="CASCADE"),
        nullable=False,
    )
    entity_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("cp_entities.id", ondelete="CASCADE"),
        nullable=False,
    )
    asset_class_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("fa_asset_classes.id", ondelete="RESTRICT"),
        nullable=False,
    )
    asset_code: Mapped[str] = mapped_column(String(100), nullable=False)
    asset_name: Mapped[str] = mapped_column(String(300), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    location: Mapped[str | None] = mapped_column(String(300), nullable=True)
    serial_number: Mapped[str | None] = mapped_column(String(200), nullable=True)
    purchase_date: Mapped[date] = mapped_column(Date, nullable=False)
    capitalisation_date: Mapped[date] = mapped_column(Date, nullable=False)
    original_cost: Mapped[Decimal] = mapped_column(Numeric(20, 4), nullable=False)
    residual_value: Mapped[Decimal] = mapped_column(Numeric(20, 4), nullable=False, server_default=text("0"), default=Decimal("0"))
    useful_life_years: Mapped[Decimal] = mapped_column(Numeric(10, 4), nullable=False)
    depreciation_method: Mapped[str] = mapped_column(String(20), nullable=False)
    it_act_block_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    disposal_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    disposal_proceeds: Mapped[Decimal | None] = mapped_column(Numeric(20, 4), nullable=True)
    gaap_overrides: Mapped[dict[str, object] | None] = mapped_column(JSONB, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"), default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        server_default=func.now(),
        onupdate=func.now(),
    )


class FaDepreciationRun(Base):
    __tablename__ = "fa_depreciation_runs"
    __table_args__ = (
        UniqueConstraint("run_reference", name="uq_fa_depreciation_runs_run_reference"),
        Index("idx_fa_depreciation_runs_tenant_id", "tenant_id"),
        Index("idx_fa_depreciation_runs_entity_id", "entity_id"),
        Index("idx_fa_depreciation_runs_asset_id", "asset_id"),
        Index("idx_fa_depreciation_runs_run_date", "run_date"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        nullable=False,
        server_default=text("gen_random_uuid()"),
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("iam_tenants.id", ondelete="CASCADE"),
        nullable=False,
    )
    entity_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("cp_entities.id", ondelete="CASCADE"),
        nullable=False,
    )
    asset_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("fa_assets.id", ondelete="CASCADE"),
        nullable=False,
    )
    run_date: Mapped[date] = mapped_column(Date, nullable=False)
    period_start: Mapped[date] = mapped_column(Date, nullable=False)
    period_end: Mapped[date] = mapped_column(Date, nullable=False)
    gaap: Mapped[str] = mapped_column(String(20), nullable=False)
    depreciation_method: Mapped[str] = mapped_column(String(20), nullable=False)
    opening_nbv: Mapped[Decimal] = mapped_column(Numeric(20, 4), nullable=False)
    depreciation_amount: Mapped[Decimal] = mapped_column(Numeric(20, 4), nullable=False)
    closing_nbv: Mapped[Decimal] = mapped_column(Numeric(20, 4), nullable=False)
    accumulated_dep: Mapped[Decimal] = mapped_column(Numeric(20, 4), nullable=False)
    run_reference: Mapped[str] = mapped_column(String(100), nullable=False)
    is_reversal: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"), default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class FaRevaluation(Base):
    __tablename__ = "fa_revaluations"
    __table_args__ = (
        Index("idx_fa_revaluations_tenant_id", "tenant_id"),
        Index("idx_fa_revaluations_entity_id", "entity_id"),
        Index("idx_fa_revaluations_asset_id", "asset_id"),
        Index("idx_fa_revaluations_revaluation_date", "revaluation_date"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        nullable=False,
        server_default=text("gen_random_uuid()"),
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("iam_tenants.id", ondelete="CASCADE"),
        nullable=False,
    )
    entity_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("cp_entities.id", ondelete="CASCADE"),
        nullable=False,
    )
    asset_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("fa_assets.id", ondelete="CASCADE"),
        nullable=False,
    )
    revaluation_date: Mapped[date] = mapped_column(Date, nullable=False)
    pre_revaluation_cost: Mapped[Decimal] = mapped_column(Numeric(20, 4), nullable=False)
    pre_revaluation_accum_dep: Mapped[Decimal] = mapped_column(Numeric(20, 4), nullable=False)
    pre_revaluation_nbv: Mapped[Decimal] = mapped_column(Numeric(20, 4), nullable=False)
    fair_value: Mapped[Decimal] = mapped_column(Numeric(20, 4), nullable=False)
    revaluation_surplus: Mapped[Decimal] = mapped_column(Numeric(20, 4), nullable=False)
    method: Mapped[str] = mapped_column(String(30), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class FaImpairment(Base):
    __tablename__ = "fa_impairments"
    __table_args__ = (
        Index("idx_fa_impairments_tenant_id", "tenant_id"),
        Index("idx_fa_impairments_entity_id", "entity_id"),
        Index("idx_fa_impairments_asset_id", "asset_id"),
        Index("idx_fa_impairments_impairment_date", "impairment_date"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        nullable=False,
        server_default=text("gen_random_uuid()"),
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("iam_tenants.id", ondelete="CASCADE"),
        nullable=False,
    )
    entity_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("cp_entities.id", ondelete="CASCADE"),
        nullable=False,
    )
    asset_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("fa_assets.id", ondelete="CASCADE"),
        nullable=False,
    )
    impairment_date: Mapped[date] = mapped_column(Date, nullable=False)
    pre_impairment_nbv: Mapped[Decimal] = mapped_column(Numeric(20, 4), nullable=False)
    recoverable_amount: Mapped[Decimal] = mapped_column(Numeric(20, 4), nullable=False)
    value_in_use: Mapped[Decimal | None] = mapped_column(Numeric(20, 4), nullable=True)
    fvlcts: Mapped[Decimal | None] = mapped_column(Numeric(20, 4), nullable=True)
    impairment_loss: Mapped[Decimal] = mapped_column(Numeric(20, 4), nullable=False)
    discount_rate: Mapped[Decimal | None] = mapped_column(Numeric(7, 4), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


__all__ = [
    "FaAssetClass",
    "FaAsset",
    "FaDepreciationRun",
    "FaRevaluation",
    "FaImpairment",
]
