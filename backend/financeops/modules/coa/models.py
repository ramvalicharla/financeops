from __future__ import annotations

import enum
import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
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


class CoaSourceType(str, enum.Enum):
    SYSTEM = "SYSTEM"
    ADMIN_TEMPLATE = "ADMIN_TEMPLATE"
    TENANT_CUSTOM = "TENANT_CUSTOM"


class CoaUploadStatus(str, enum.Enum):
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"


class CoaUploadMode(str, enum.Enum):
    APPEND = "APPEND"
    REPLACE = "REPLACE"
    VALIDATE_ONLY = "VALIDATE_ONLY"


class CoaIndustryTemplate(Base):
    __tablename__ = "coa_industry_templates"
    __table_args__ = (
        UniqueConstraint("code", name="uq_coa_industry_templates_code"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        nullable=False,
        server_default=text("gen_random_uuid()"),
    )
    code: Mapped[str] = mapped_column(String(50), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"), default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        server_default=func.now(),
        onupdate=func.now(),
    )

    account_groups: Mapped[list[CoaAccountGroup]] = relationship(
        back_populates="industry_template",
        lazy="noload",
    )
    ledger_accounts: Mapped[list[CoaLedgerAccount]] = relationship(
        back_populates="industry_template",
        lazy="noload",
    )


class CoaFsClassification(Base):
    __tablename__ = "coa_fs_classifications"
    __table_args__ = (
        UniqueConstraint("code", name="uq_coa_fs_classifications_code"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        nullable=False,
        server_default=text("gen_random_uuid()"),
    )
    code: Mapped[str] = mapped_column(String(50), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"), default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())

    fs_schedules: Mapped[list[CoaFsSchedule]] = relationship(
        back_populates="fs_classification",
        lazy="noload",
    )


class CoaFsSchedule(Base):
    __tablename__ = "coa_fs_schedules"
    __table_args__ = (
        UniqueConstraint("gaap", "code", name="uq_coa_fs_schedules_gaap_code"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        nullable=False,
        server_default=text("gen_random_uuid()"),
    )
    fs_classification_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("coa_fs_classifications.id", ondelete="CASCADE"),
        nullable=False,
    )
    gaap: Mapped[str] = mapped_column(String(20), nullable=False)
    code: Mapped[str] = mapped_column(String(50), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    schedule_number: Mapped[str | None] = mapped_column(String(20), nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"), default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())

    fs_classification: Mapped[CoaFsClassification] = relationship(
        back_populates="fs_schedules",
        lazy="noload",
    )
    line_items: Mapped[list[CoaFsLineItem]] = relationship(
        back_populates="fs_schedule",
        lazy="noload",
    )
    gaap_mappings: Mapped[list[CoaGaapMapping]] = relationship(
        back_populates="fs_schedule",
        lazy="noload",
    )


class CoaFsLineItem(Base):
    __tablename__ = "coa_fs_line_items"
    __table_args__ = (
        UniqueConstraint("fs_schedule_id", "code", name="uq_coa_fs_line_items_schedule_code"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        nullable=False,
        server_default=text("gen_random_uuid()"),
    )
    fs_schedule_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("coa_fs_schedules.id", ondelete="CASCADE"),
        nullable=False,
    )
    code: Mapped[str] = mapped_column(String(50), nullable=False)
    name: Mapped[str] = mapped_column(String(300), nullable=False)
    bs_pl_flag: Mapped[str | None] = mapped_column(String(20), nullable=True)
    asset_liability_class: Mapped[str | None] = mapped_column(String(20), nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"), default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())

    fs_schedule: Mapped[CoaFsSchedule] = relationship(back_populates="line_items", lazy="noload")
    sublines: Mapped[list[CoaFsSubline]] = relationship(back_populates="fs_line_item", lazy="noload")
    gaap_mappings: Mapped[list[CoaGaapMapping]] = relationship(back_populates="fs_line_item", lazy="noload")


class CoaFsSubline(Base):
    __tablename__ = "coa_fs_sublines"
    __table_args__ = (
        UniqueConstraint("fs_line_item_id", "code", name="uq_coa_fs_sublines_line_code"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        nullable=False,
        server_default=text("gen_random_uuid()"),
    )
    fs_line_item_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("coa_fs_line_items.id", ondelete="CASCADE"),
        nullable=False,
    )
    code: Mapped[str] = mapped_column(String(50), nullable=False)
    name: Mapped[str] = mapped_column(String(300), nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"), default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())

    fs_line_item: Mapped[CoaFsLineItem] = relationship(back_populates="sublines", lazy="noload")
    account_groups: Mapped[list[CoaAccountGroup]] = relationship(back_populates="fs_subline", lazy="noload")
    gaap_mappings: Mapped[list[CoaGaapMapping]] = relationship(back_populates="fs_subline", lazy="noload")


class CoaAccountGroup(Base):
    __tablename__ = "coa_account_groups"
    __table_args__ = (
        UniqueConstraint("industry_template_id", "code", name="uq_coa_account_groups_template_code"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        nullable=False,
        server_default=text("gen_random_uuid()"),
    )
    industry_template_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("coa_industry_templates.id", ondelete="CASCADE"),
        nullable=False,
    )
    fs_subline_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("coa_fs_sublines.id", ondelete="SET NULL"),
        nullable=True,
    )
    code: Mapped[str] = mapped_column(String(50), nullable=False)
    name: Mapped[str] = mapped_column(String(300), nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"), default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())

    industry_template: Mapped[CoaIndustryTemplate] = relationship(back_populates="account_groups", lazy="noload")
    fs_subline: Mapped[CoaFsSubline | None] = relationship(back_populates="account_groups", lazy="noload")
    subgroups: Mapped[list[CoaAccountSubgroup]] = relationship(back_populates="account_group", lazy="noload")


class CoaAccountSubgroup(Base):
    __tablename__ = "coa_account_subgroups"
    __table_args__ = (
        UniqueConstraint("account_group_id", "code", name="uq_coa_account_subgroups_group_code"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        nullable=False,
        server_default=text("gen_random_uuid()"),
    )
    account_group_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("coa_account_groups.id", ondelete="CASCADE"),
        nullable=False,
    )
    code: Mapped[str] = mapped_column(String(50), nullable=False)
    name: Mapped[str] = mapped_column(String(300), nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"), default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())

    account_group: Mapped[CoaAccountGroup] = relationship(back_populates="subgroups", lazy="noload")
    ledger_accounts: Mapped[list[CoaLedgerAccount]] = relationship(back_populates="account_subgroup", lazy="noload")
    tenant_accounts: Mapped[list[TenantCoaAccount]] = relationship(back_populates="parent_subgroup", lazy="noload")


class CoaLedgerAccount(Base):
    __tablename__ = "coa_ledger_accounts"
    __table_args__ = (
        UniqueConstraint("tenant_id", "code", name="uq_coa_ledger_accounts_tenant_code"),
        Index(
            "uq_coa_ledger_accounts_global_code_ver",
            "industry_template_id",
            "source_type",
            "version",
            "code",
            unique=True,
            postgresql_where=text("tenant_id IS NULL"),
        ),
        Index(
            "uq_coa_ledger_accounts_tenant_code_ver",
            "industry_template_id",
            "tenant_id",
            "source_type",
            "version",
            "code",
            unique=True,
            postgresql_where=text("tenant_id IS NOT NULL"),
        ),
        Index("idx_coa_ledger_accounts_code", "code"),
        Index("idx_coa_ledger_accounts_industry_template_id", "industry_template_id"),
        Index("idx_coa_ledger_accounts_tenant_id", "tenant_id"),
        Index("idx_coa_ledger_accounts_source_type", "source_type"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        nullable=False,
        server_default=text("gen_random_uuid()"),
    )
    account_subgroup_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("coa_account_subgroups.id", ondelete="CASCADE"),
        nullable=False,
    )
    industry_template_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("coa_industry_templates.id", ondelete="CASCADE"),
        nullable=False,
    )
    tenant_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("iam_tenants.id", ondelete="SET NULL"),
        nullable=True,
    )
    code: Mapped[str] = mapped_column(String(50), nullable=False)
    name: Mapped[str] = mapped_column(String(300), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_type: Mapped[CoaSourceType] = mapped_column(
        Enum(CoaSourceType, name="coa_source_type_enum"),
        nullable=False,
        server_default=text("'SYSTEM'::coa_source_type_enum"),
        default=CoaSourceType.SYSTEM,
    )
    version: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        server_default=text("1"),
        default=1,
    )
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("iam_users.id", ondelete="SET NULL"),
        nullable=True,
    )

    normal_balance: Mapped[str] = mapped_column(String(10), nullable=False)
    cash_flow_tag: Mapped[str | None] = mapped_column(String(20), nullable=True)
    cash_flow_method: Mapped[str | None] = mapped_column(String(10), nullable=True)
    bs_pl_flag: Mapped[str | None] = mapped_column(String(20), nullable=True)
    asset_liability_class: Mapped[str | None] = mapped_column(String(20), nullable=True)

    is_monetary: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"), default=False)
    is_related_party: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"), default=False)
    is_tax_deductible: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"), default=True)
    is_control_account: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"), default=False)

    notes_reference: Mapped[str | None] = mapped_column(String(100), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"), default=True)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        server_default=func.now(),
        onupdate=func.now(),
    )

    account_subgroup: Mapped[CoaAccountSubgroup] = relationship(back_populates="ledger_accounts", lazy="noload")
    industry_template: Mapped[CoaIndustryTemplate] = relationship(back_populates="ledger_accounts", lazy="noload")
    gaap_mappings: Mapped[list[CoaGaapMapping]] = relationship(back_populates="ledger_account", lazy="noload")
    tenant_accounts: Mapped[list[TenantCoaAccount]] = relationship(back_populates="ledger_account", lazy="noload")


class CoaGaapMapping(Base):
    __tablename__ = "coa_gaap_mappings"
    __table_args__ = (
        UniqueConstraint("ledger_account_id", "gaap", name="uq_coa_gaap_mappings_ledger_gaap"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        nullable=False,
        server_default=text("gen_random_uuid()"),
    )
    ledger_account_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("coa_ledger_accounts.id", ondelete="CASCADE"),
        nullable=False,
    )
    gaap: Mapped[str] = mapped_column(String(20), nullable=False)
    fs_schedule_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("coa_fs_schedules.id", ondelete="CASCADE"),
        nullable=False,
    )
    fs_line_item_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("coa_fs_line_items.id", ondelete="CASCADE"),
        nullable=False,
    )
    fs_subline_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("coa_fs_sublines.id", ondelete="SET NULL"),
        nullable=True,
    )
    presentation_label: Mapped[str | None] = mapped_column(String(300), nullable=True)
    sort_order: Mapped[int | None] = mapped_column(Integer, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"), default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())

    ledger_account: Mapped[CoaLedgerAccount] = relationship(back_populates="gaap_mappings", lazy="noload")
    fs_schedule: Mapped[CoaFsSchedule] = relationship(back_populates="gaap_mappings", lazy="noload")
    fs_line_item: Mapped[CoaFsLineItem] = relationship(back_populates="gaap_mappings", lazy="noload")
    fs_subline: Mapped[CoaFsSubline | None] = relationship(back_populates="gaap_mappings", lazy="noload")


class TenantCoaAccount(Base):
    __tablename__ = "tenant_coa_accounts"
    __table_args__ = (
        UniqueConstraint("tenant_id", "account_code", name="uq_tenant_coa_accounts_tenant_code"),
        Index("idx_tenant_coa_accounts_tenant_id", "tenant_id"),
        Index("idx_tenant_coa_accounts_ledger_account_id", "ledger_account_id"),
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
    ledger_account_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("coa_ledger_accounts.id", ondelete="SET NULL"),
        nullable=True,
    )
    parent_subgroup_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("coa_account_subgroups.id", ondelete="RESTRICT"),
        nullable=True,
    )
    account_code: Mapped[str] = mapped_column(String(50), nullable=False)
    display_name: Mapped[str] = mapped_column(String(300), nullable=False)
    is_custom: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"), default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"), default=True)
    default_cost_centre_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    default_location_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    sort_order: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        server_default=func.now(),
        onupdate=func.now(),
    )

    ledger_account: Mapped[CoaLedgerAccount | None] = relationship(back_populates="tenant_accounts", lazy="noload")
    parent_subgroup: Mapped[CoaAccountSubgroup | None] = relationship(back_populates="tenant_accounts", lazy="noload")
    erp_mappings: Mapped[list[ErpAccountMapping]] = relationship(back_populates="tenant_coa_account", lazy="noload")


class ErpAccountMapping(Base):
    __tablename__ = "erp_account_mappings"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "entity_id",
            "erp_connector_type",
            "erp_account_code",
            name="uq_erp_account_mappings_scope_code",
        ),
        Index("idx_erp_account_mappings_tenant_id", "tenant_id"),
        Index("idx_erp_account_mappings_entity_id", "entity_id"),
        Index("idx_erp_account_mappings_erp_connector_type", "erp_connector_type"),
        Index("idx_erp_account_mappings_is_confirmed", "is_confirmed"),
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
    erp_connector_type: Mapped[str] = mapped_column(String(50), nullable=False)
    erp_account_code: Mapped[str] = mapped_column(String(200), nullable=False)
    erp_account_name: Mapped[str] = mapped_column(String(300), nullable=False)
    erp_account_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    tenant_coa_account_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tenant_coa_accounts.id", ondelete="SET NULL"),
        nullable=True,
    )
    mapping_confidence: Mapped[Decimal | None] = mapped_column(Numeric(5, 4), nullable=True)
    is_auto_mapped: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"), default=False)
    is_confirmed: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"), default=False)
    confirmed_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("iam_users.id", ondelete="SET NULL"),
        nullable=True,
    )
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"), default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        server_default=func.now(),
        onupdate=func.now(),
    )

    tenant_coa_account: Mapped[TenantCoaAccount | None] = relationship(back_populates="erp_mappings", lazy="noload")


class CoaUploadBatch(Base):
    __tablename__ = "coa_upload_batches"
    __table_args__ = (
        Index("idx_coa_upload_batches_tenant_id", "tenant_id"),
        Index("idx_coa_upload_batches_template_id", "template_id"),
        Index("idx_coa_upload_batches_source_type", "source_type"),
        Index("idx_coa_upload_batches_upload_status", "upload_status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        nullable=False,
        server_default=text("gen_random_uuid()"),
    )
    tenant_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("iam_tenants.id", ondelete="SET NULL"),
        nullable=True,
    )
    template_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("coa_industry_templates.id", ondelete="SET NULL"),
        nullable=True,
    )
    source_type: Mapped[CoaSourceType] = mapped_column(
        Enum(CoaSourceType, name="coa_source_type_enum"),
        nullable=False,
    )
    upload_mode: Mapped[CoaUploadMode] = mapped_column(
        Enum(CoaUploadMode, name="coa_upload_mode_enum"),
        nullable=False,
        server_default=text("'APPEND'::coa_upload_mode_enum"),
        default=CoaUploadMode.APPEND,
    )
    file_name: Mapped[str] = mapped_column(String(255), nullable=False)
    upload_status: Mapped[CoaUploadStatus] = mapped_column(
        Enum(CoaUploadStatus, name="coa_upload_status_enum"),
        nullable=False,
        server_default=text("'PENDING'::coa_upload_status_enum"),
        default=CoaUploadStatus.PENDING,
    )
    error_log: Mapped[dict[str, object] | None] = mapped_column(JSONB, nullable=True)
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("iam_users.id", ondelete="SET NULL"),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class CoaUploadStagingRow(Base):
    __tablename__ = "coa_upload_staging_rows"
    __table_args__ = (
        Index("idx_coa_upload_staging_rows_batch_id", "batch_id"),
        Index("idx_coa_upload_staging_rows_is_valid", "is_valid"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        nullable=False,
        server_default=text("gen_random_uuid()"),
    )
    batch_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("coa_upload_batches.id", ondelete="CASCADE"),
        nullable=False,
    )
    tenant_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("iam_tenants.id", ondelete="SET NULL"),
        nullable=True,
    )
    template_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("coa_industry_templates.id", ondelete="SET NULL"),
        nullable=True,
    )
    row_number: Mapped[int] = mapped_column(Integer, nullable=False)
    group_code: Mapped[str] = mapped_column(String(50), nullable=False)
    group_name: Mapped[str] = mapped_column(String(300), nullable=False)
    subgroup_code: Mapped[str] = mapped_column(String(50), nullable=False)
    subgroup_name: Mapped[str] = mapped_column(String(300), nullable=False)
    ledger_code: Mapped[str] = mapped_column(String(50), nullable=False)
    ledger_name: Mapped[str] = mapped_column(String(300), nullable=False)
    ledger_type: Mapped[str] = mapped_column(String(20), nullable=False)
    is_control_account: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default=text("false"),
        default=False,
    )
    validation_errors: Mapped[list[dict[str, object]] | None] = mapped_column(JSONB, nullable=True)
    is_valid: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default=text("true"),
        default=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )


__all__ = [
    "CoaSourceType",
    "CoaUploadStatus",
    "CoaUploadMode",
    "CoaIndustryTemplate",
    "CoaFsClassification",
    "CoaFsSchedule",
    "CoaFsLineItem",
    "CoaFsSubline",
    "CoaAccountGroup",
    "CoaAccountSubgroup",
    "CoaLedgerAccount",
    "CoaGaapMapping",
    "TenantCoaAccount",
    "ErpAccountMapping",
    "CoaUploadBatch",
    "CoaUploadStagingRow",
]
