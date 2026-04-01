from __future__ import annotations

import enum
import uuid
from datetime import datetime

from sqlalchemy import (
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from financeops.db.base import Base


class ErpConnectorStatus(str, enum.Enum):
    ACTIVE = "ACTIVE"
    INACTIVE = "INACTIVE"
    ERROR = "ERROR"


class ErpAuthType(str, enum.Enum):
    API_KEY = "API_KEY"
    OAUTH = "OAUTH"
    BASIC = "BASIC"


class ErpSyncType(str, enum.Enum):
    IMPORT = "IMPORT"
    EXPORT = "EXPORT"


class ErpSyncModule(str, enum.Enum):
    COA = "COA"
    JOURNALS = "JOURNALS"
    VENDORS = "VENDORS"
    CUSTOMERS = "CUSTOMERS"


class ErpSyncStatus(str, enum.Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"


class ErpMasterEntityType(str, enum.Enum):
    VENDOR = "VENDOR"
    CUSTOMER = "CUSTOMER"


class ErpConnector(Base):
    __tablename__ = "erp_connectors"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "org_entity_id",
            "erp_type",
            name="uq_erp_connectors_tenant_entity_type",
        ),
        Index("ix_erp_connectors_tenant", "tenant_id"),
        Index("ix_erp_connectors_entity", "tenant_id", "org_entity_id"),
        Index("ix_erp_connectors_status", "tenant_id", "status"),
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
        ForeignKey("cp_entities.id", ondelete="CASCADE"),
        nullable=False,
    )
    erp_type: Mapped[str] = mapped_column(String(32), nullable=False)
    connection_config: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False, default=dict)
    auth_type: Mapped[ErpAuthType] = mapped_column(
        Enum(ErpAuthType, name="erp_auth_type_enum"),
        nullable=False,
    )
    status: Mapped[ErpConnectorStatus] = mapped_column(
        Enum(ErpConnectorStatus, name="erp_connector_status_enum"),
        nullable=False,
        server_default=text("'ACTIVE'::erp_connector_status_enum"),
        default=ErpConnectorStatus.ACTIVE,
    )
    last_sync_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
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
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        server_default=func.now(),
        onupdate=func.now(),
    )


class ErpSyncJob(Base):
    __tablename__ = "erp_sync_jobs"
    __table_args__ = (
        Index("ix_erp_sync_jobs_tenant", "tenant_id"),
        Index("ix_erp_sync_jobs_connector", "tenant_id", "erp_connector_id"),
        Index("ix_erp_sync_jobs_status", "tenant_id", "status"),
        Index("ix_erp_sync_jobs_module", "tenant_id", "module"),
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
        ForeignKey("cp_entities.id", ondelete="CASCADE"),
        nullable=False,
    )
    erp_connector_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("erp_connectors.id", ondelete="CASCADE"),
        nullable=False,
    )
    sync_type: Mapped[ErpSyncType] = mapped_column(
        Enum(ErpSyncType, name="erp_sync_type_enum"),
        nullable=False,
    )
    module: Mapped[ErpSyncModule] = mapped_column(
        Enum(ErpSyncModule, name="erp_sync_module_enum"),
        nullable=False,
    )
    status: Mapped[ErpSyncStatus] = mapped_column(
        Enum(ErpSyncStatus, name="erp_sync_status_enum"),
        nullable=False,
        server_default=text("'PENDING'::erp_sync_status_enum"),
        default=ErpSyncStatus.PENDING,
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    retry_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        server_default=text("0"),
        default=0,
    )
    request_payload: Mapped[dict[str, object] | None] = mapped_column(JSONB, nullable=True)
    result_summary: Mapped[dict[str, object] | None] = mapped_column(JSONB, nullable=True)
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
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        server_default=func.now(),
        onupdate=func.now(),
    )


class ErpSyncLog(Base):
    __tablename__ = "erp_sync_logs"
    __table_args__ = (
        Index("ix_erp_sync_logs_job", "job_id"),
        Index("ix_erp_sync_logs_created", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        nullable=False,
        server_default=text("gen_random_uuid()"),
    )
    job_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("erp_sync_jobs.id", ondelete="CASCADE"),
        nullable=False,
    )
    payload_json: Mapped[dict[str, object] | None] = mapped_column(JSONB, nullable=True)
    result_json: Mapped[dict[str, object] | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )


class ErpCoaMapping(Base):
    __tablename__ = "erp_coa_mappings"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "erp_connector_id",
            "erp_account_id",
            name="uq_erp_coa_mappings_connector_account",
        ),
        Index("ix_erp_coa_mappings_tenant", "tenant_id"),
        Index("ix_erp_coa_mappings_internal", "tenant_id", "internal_account_id"),
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
    erp_connector_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("erp_connectors.id", ondelete="CASCADE"),
        nullable=False,
    )
    erp_account_id: Mapped[str] = mapped_column(String(256), nullable=False)
    internal_account_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tenant_coa_accounts.id", ondelete="SET NULL"),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        server_default=func.now(),
        onupdate=func.now(),
    )


class ErpJournalMapping(Base):
    __tablename__ = "erp_journal_mappings"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "erp_connector_id",
            "erp_journal_id",
            name="uq_erp_journal_mappings_connector_external",
        ),
        UniqueConstraint(
            "tenant_id",
            "internal_journal_id",
            name="uq_erp_journal_mappings_internal_journal",
        ),
        Index("ix_erp_journal_mappings_tenant", "tenant_id"),
        Index("ix_erp_journal_mappings_connector", "tenant_id", "erp_connector_id"),
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
    erp_connector_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("erp_connectors.id", ondelete="CASCADE"),
        nullable=False,
    )
    internal_journal_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("accounting_jv_aggregates.id", ondelete="CASCADE"),
        nullable=False,
    )
    erp_journal_id: Mapped[str] = mapped_column(String(256), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )


class ErpMasterMapping(Base):
    __tablename__ = "erp_master_mappings"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "erp_connector_id",
            "entity_type",
            "erp_id",
            name="uq_erp_master_mappings_connector_entity",
        ),
        Index("ix_erp_master_mappings_tenant_type", "tenant_id", "entity_type"),
        Index("ix_erp_master_mappings_entity_scope", "tenant_id", "org_entity_id"),
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
        ForeignKey("cp_entities.id", ondelete="CASCADE"),
        nullable=False,
    )
    erp_connector_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("erp_connectors.id", ondelete="CASCADE"),
        nullable=False,
    )
    entity_type: Mapped[ErpMasterEntityType] = mapped_column(
        Enum(ErpMasterEntityType, name="erp_master_entity_type_enum"),
        nullable=False,
    )
    erp_id: Mapped[str] = mapped_column(String(256), nullable=False)
    internal_id: Mapped[str] = mapped_column(String(256), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        server_default=func.now(),
        onupdate=func.now(),
    )


__all__ = [
    "ErpAuthType",
    "ErpConnector",
    "ErpConnectorStatus",
    "ErpCoaMapping",
    "ErpJournalMapping",
    "ErpMasterEntityType",
    "ErpMasterMapping",
    "ErpSyncJob",
    "ErpSyncLog",
    "ErpSyncModule",
    "ErpSyncStatus",
    "ErpSyncType",
]
