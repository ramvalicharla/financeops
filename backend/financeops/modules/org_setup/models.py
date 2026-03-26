from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    CheckConstraint,
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
from sqlalchemy.orm import Mapped, mapped_column, relationship

from financeops.db.base import Base


class OrgGroup(Base):
    __tablename__ = "org_groups"
    __table_args__ = (
        UniqueConstraint("tenant_id", name="uq_org_groups_tenant_id"),
        Index("idx_org_groups_tenant_id", "tenant_id"),
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
    group_name: Mapped[str] = mapped_column(String(300), nullable=False)
    country_of_incorp: Mapped[str] = mapped_column(String(100), nullable=False)
    country_code: Mapped[str] = mapped_column(String(3), nullable=False)
    functional_currency: Mapped[str] = mapped_column(String(10), nullable=False)
    reporting_currency: Mapped[str] = mapped_column(String(10), nullable=False)
    logo_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    website: Mapped[str | None] = mapped_column(String(300), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        server_default=func.now(),
        onupdate=func.now(),
    )

    entities: Mapped[list[OrgEntity]] = relationship(back_populates="org_group", lazy="noload")


class OrgEntity(Base):
    __tablename__ = "org_entities"
    __table_args__ = (
        CheckConstraint("fiscal_year_start >= 1 AND fiscal_year_start <= 12", name="ck_org_entities_fiscal_year_start"),
        Index("idx_org_entities_tenant_id", "tenant_id"),
        Index("idx_org_entities_org_group_id", "org_group_id"),
        Index("idx_org_entities_cp_entity_id", "cp_entity_id"),
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
    org_group_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("org_groups.id", ondelete="CASCADE"),
        nullable=False,
    )
    cp_entity_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("cp_entities.id", ondelete="SET NULL"),
        nullable=True,
    )
    legal_name: Mapped[str] = mapped_column(String(300), nullable=False)
    display_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    entity_type: Mapped[str] = mapped_column(String(50), nullable=False)
    country_code: Mapped[str] = mapped_column(String(3), nullable=False)
    state_code: Mapped[str | None] = mapped_column(String(10), nullable=True)
    functional_currency: Mapped[str] = mapped_column(String(10), nullable=False)
    reporting_currency: Mapped[str] = mapped_column(String(10), nullable=False)
    fiscal_year_start: Mapped[int] = mapped_column(Integer, nullable=False)
    applicable_gaap: Mapped[str] = mapped_column(String(20), nullable=False)
    industry_template_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("coa_industry_templates.id", ondelete="SET NULL"),
        nullable=True,
    )
    incorporation_number: Mapped[str | None] = mapped_column(String(100), nullable=True)
    pan: Mapped[str | None] = mapped_column(String(20), nullable=True)
    tan: Mapped[str | None] = mapped_column(String(20), nullable=True)
    cin: Mapped[str | None] = mapped_column(String(30), nullable=True)
    gstin: Mapped[str | None] = mapped_column(String(20), nullable=True)
    lei: Mapped[str | None] = mapped_column(String(30), nullable=True)
    tax_jurisdiction: Mapped[str | None] = mapped_column(String(100), nullable=True)
    tax_rate: Mapped[Decimal | None] = mapped_column(Numeric(5, 4), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"), default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        server_default=func.now(),
        onupdate=func.now(),
    )

    org_group: Mapped[OrgGroup] = relationship(back_populates="entities", lazy="noload")
    erp_configs: Mapped[list[OrgEntityErpConfig]] = relationship(back_populates="org_entity", lazy="noload")
    parent_relationships: Mapped[list[OrgOwnership]] = relationship(
        "OrgOwnership",
        foreign_keys="OrgOwnership.parent_entity_id",
        back_populates="parent_entity",
        lazy="noload",
    )
    child_relationships: Mapped[list[OrgOwnership]] = relationship(
        "OrgOwnership",
        foreign_keys="OrgOwnership.child_entity_id",
        back_populates="child_entity",
        lazy="noload",
    )


class OrgOwnership(Base):
    __tablename__ = "org_ownership"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "parent_entity_id",
            "child_entity_id",
            "effective_from",
            name="uq_org_ownership_scope_effective_from",
        ),
        Index("idx_org_ownership_tenant_id", "tenant_id"),
        Index("idx_org_ownership_parent_entity_id", "parent_entity_id"),
        Index("idx_org_ownership_child_entity_id", "child_entity_id"),
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
    parent_entity_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("org_entities.id", ondelete="CASCADE"),
        nullable=False,
    )
    child_entity_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("org_entities.id", ondelete="CASCADE"),
        nullable=False,
    )
    ownership_pct: Mapped[Decimal] = mapped_column(Numeric(7, 4), nullable=False)
    consolidation_method: Mapped[str] = mapped_column(String(30), nullable=False)
    effective_from: Mapped[date] = mapped_column(Date, nullable=False)
    effective_to: Mapped[date | None] = mapped_column(Date, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())

    parent_entity: Mapped[OrgEntity] = relationship(
        "OrgEntity",
        foreign_keys=[parent_entity_id],
        back_populates="parent_relationships",
        lazy="noload",
    )
    child_entity: Mapped[OrgEntity] = relationship(
        "OrgEntity",
        foreign_keys=[child_entity_id],
        back_populates="child_relationships",
        lazy="noload",
    )


class OrgEntityErpConfig(Base):
    __tablename__ = "org_entity_erp_configs"
    __table_args__ = (
        Index("idx_org_entity_erp_configs_tenant_id", "tenant_id"),
        Index("idx_org_entity_erp_configs_org_entity_id", "org_entity_id"),
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
    org_entity_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("org_entities.id", ondelete="CASCADE"),
        nullable=False,
    )
    erp_type: Mapped[str] = mapped_column(String(50), nullable=False)
    erp_version: Mapped[str | None] = mapped_column(String(50), nullable=True)
    connection_config: Mapped[dict[str, object] | None] = mapped_column(JSONB, nullable=True)
    is_primary: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"), default=True)
    connection_tested: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"), default=False)
    connection_tested_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"), default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        server_default=func.now(),
        onupdate=func.now(),
    )

    org_entity: Mapped[OrgEntity] = relationship(back_populates="erp_configs", lazy="noload")


class OrgSetupProgress(Base):
    __tablename__ = "org_setup_progress"
    __table_args__ = (
        UniqueConstraint("tenant_id", name="uq_org_setup_progress_tenant_id"),
        Index("idx_org_setup_progress_tenant_id", "tenant_id"),
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
    current_step: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("1"), default=1)
    step1_data: Mapped[dict[str, object] | None] = mapped_column(JSONB, nullable=True)
    step2_data: Mapped[dict[str, object] | None] = mapped_column(JSONB, nullable=True)
    step3_data: Mapped[dict[str, object] | None] = mapped_column(JSONB, nullable=True)
    step4_data: Mapped[dict[str, object] | None] = mapped_column(JSONB, nullable=True)
    step5_data: Mapped[dict[str, object] | None] = mapped_column(JSONB, nullable=True)
    step6_data: Mapped[dict[str, object] | None] = mapped_column(JSONB, nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        server_default=func.now(),
        onupdate=func.now(),
    )


__all__ = [
    "OrgGroup",
    "OrgEntity",
    "OrgOwnership",
    "OrgEntityErpConfig",
    "OrgSetupProgress",
]
