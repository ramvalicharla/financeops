from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Any

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from financeops.db.base import Base, FinancialBase


_STATUS_CHECK = "status IN ('candidate','active','superseded','retired','rejected')"


class ExternalConnection(FinancialBase):
    __tablename__ = "external_connections"
    __table_args__ = (
        UniqueConstraint("tenant_id", "connection_code", name="uq_external_connections_code"),
        CheckConstraint(
            "connection_status IN ('draft','active','suspended','revoked')",
            name="ck_external_connections_status",
        ),
        Index("idx_external_connections_lookup", "tenant_id", "organisation_id", "connection_status", "created_at"),
    )

    organisation_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    entity_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    connector_type: Mapped[str] = mapped_column(String(64), nullable=False)
    connection_code: Mapped[str] = mapped_column(String(128), nullable=False)
    connection_name: Mapped[str] = mapped_column(String(255), nullable=False)
    source_system_instance_id: Mapped[str] = mapped_column(String(255), nullable=False)
    data_residency_region: Mapped[str] = mapped_column(String(64), nullable=False, default="in")
    pii_masking_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    consent_reference: Mapped[str | None] = mapped_column(String(255), nullable=True)
    pinned_connector_version: Mapped[str | None] = mapped_column(String(64), nullable=True)
    connection_status: Mapped[str] = mapped_column(String(32), nullable=False, default="draft")
    secret_ref: Mapped[str | None] = mapped_column(Text, nullable=True)
    encrypted_tokens: Mapped[str | None] = mapped_column(Text, nullable=True)
    token_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    token_refreshed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    oauth_scopes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)


class ErpOAuthSession(Base):
    __tablename__ = "erp_oauth_sessions"
    __table_args__ = (
        UniqueConstraint("state_token", name="uq_erp_oauth_sessions_state_token"),
        Index("idx_erp_oauth_sessions_connection_status", "connection_id", "status"),
        Index("idx_erp_oauth_sessions_tenant_created", "tenant_id", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    entity_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("cp_entities.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    connection_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("external_connections.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    provider: Mapped[str] = mapped_column(String(32), nullable=False)
    state_token: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    code_verifier_enc: Mapped[str] = mapped_column(Text, nullable=False)
    redirect_uri: Mapped[str] = mapped_column(Text, nullable=False)
    scopes: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="PENDING")
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    consumed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    initiated_by_user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    encrypted_tokens: Mapped[str | None] = mapped_column(Text, nullable=True)
    token_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("now()"),
    )


class ExternalConnectionVersion(FinancialBase):
    __tablename__ = "external_connection_versions"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "connection_id",
            "version_no",
            name="uq_external_connection_versions_number",
        ),
        CheckConstraint(_STATUS_CHECK, name="ck_external_connection_versions_status"),
        Index("idx_external_connection_versions_lookup", "tenant_id", "connection_id", "version_no", "created_at"),
    )

    connection_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("external_connections.id", ondelete="RESTRICT"),
        nullable=False,
    )
    version_no: Mapped[int] = mapped_column(Integer, nullable=False)
    version_token: Mapped[str] = mapped_column(String(64), nullable=False)
    config_snapshot_json: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    supersedes_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("external_connection_versions.id", ondelete="RESTRICT"),
        nullable=True,
    )
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="candidate")
    created_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)


class ExternalSyncDefinition(FinancialBase):
    __tablename__ = "external_sync_definitions"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "organisation_id",
            "definition_code",
            name="uq_external_sync_definitions_code",
        ),
        CheckConstraint(
            "definition_status IN ('draft','active','retired')",
            name="ck_external_sync_definitions_status",
        ),
        Index("idx_external_sync_definitions_lookup", "tenant_id", "organisation_id", "definition_status", "created_at"),
    )

    organisation_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    entity_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    connection_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("external_connections.id", ondelete="RESTRICT"),
        nullable=False,
    )
    definition_code: Mapped[str] = mapped_column(String(128), nullable=False)
    definition_name: Mapped[str] = mapped_column(String(255), nullable=False)
    dataset_type: Mapped[str] = mapped_column(String(128), nullable=False)
    sync_mode: Mapped[str] = mapped_column(String(32), nullable=False, default="full")
    definition_status: Mapped[str] = mapped_column(String(32), nullable=False, default="draft")
    created_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)


class ExternalSyncDefinitionVersion(FinancialBase):
    __tablename__ = "external_sync_definition_versions"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "sync_definition_id",
            "version_no",
            name="uq_external_sync_definition_versions_number",
        ),
        CheckConstraint(_STATUS_CHECK, name="ck_external_sync_definition_versions_status"),
        Index("idx_external_sync_definition_versions_lookup", "tenant_id", "sync_definition_id", "version_no", "created_at"),
    )

    sync_definition_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("external_sync_definitions.id", ondelete="RESTRICT"),
        nullable=False,
    )
    version_no: Mapped[int] = mapped_column(Integer, nullable=False)
    version_token: Mapped[str] = mapped_column(String(64), nullable=False)
    period_resolution_json: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    extraction_scope_json: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    supersedes_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("external_sync_definition_versions.id", ondelete="RESTRICT"),
        nullable=True,
    )
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="candidate")
    created_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)


class ExternalSyncRun(FinancialBase):
    __tablename__ = "external_sync_runs"
    __table_args__ = (
        UniqueConstraint("tenant_id", "run_token", name="uq_external_sync_runs_run_token"),
        UniqueConstraint("tenant_id", "idempotency_key", name="uq_external_sync_runs_idempotency"),
        CheckConstraint(
            "run_status IN ('created','running','halted','failed','completed','published','paused','drift_alert')",
            name="ck_external_sync_runs_status",
        ),
        Index("idx_external_sync_runs_lookup", "tenant_id", "organisation_id", "dataset_type", "created_at"),
    )

    organisation_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    entity_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    connection_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("external_connections.id", ondelete="RESTRICT"), nullable=False
    )
    sync_definition_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("external_sync_definitions.id", ondelete="RESTRICT"),
        nullable=False,
    )
    sync_definition_version_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("external_sync_definition_versions.id", ondelete="RESTRICT"),
        nullable=False,
    )
    dataset_type: Mapped[str] = mapped_column(String(128), nullable=False)
    reporting_period_label: Mapped[str | None] = mapped_column(String(64), nullable=True)
    run_token: Mapped[str] = mapped_column(String(64), nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False)
    source_airlock_item_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("airlock_items.id", ondelete="SET NULL"),
        nullable=True,
    )
    source_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    source_external_ref: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_by_intent_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("canonical_intents.id", ondelete="SET NULL"),
        nullable=True,
    )
    recorded_by_job_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("canonical_jobs.id", ondelete="SET NULL"),
        nullable=True,
    )
    run_status: Mapped[str] = mapped_column(String(32), nullable=False, default="created")
    raw_snapshot_payload_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    mapping_version_token: Mapped[str | None] = mapped_column(String(64), nullable=True)
    normalization_version: Mapped[str | None] = mapped_column(String(64), nullable=True)
    validation_summary_json: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    extraction_total_records: Mapped[int | None] = mapped_column(Integer, nullable=True)
    extraction_fetched_records: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    extraction_checkpoint: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    extraction_chunk_size: Mapped[int] = mapped_column(Integer, nullable=False, default=500)
    is_resumable: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    resumed_from_run_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("external_sync_runs.id", ondelete="RESTRICT"), nullable=True
    )
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)


class ExternalRawSnapshot(FinancialBase):
    __tablename__ = "external_raw_snapshots"
    __table_args__ = (
        UniqueConstraint("tenant_id", "snapshot_token", name="uq_external_raw_snapshots_token"),
        Index("idx_external_raw_snapshots_run", "tenant_id", "sync_run_id", "created_at"),
    )

    entity_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("cp_entities.id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
        comment="Entity scope for multi-entity tenants",
    )
    sync_run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("external_sync_runs.id", ondelete="RESTRICT"), nullable=False
    )
    snapshot_token: Mapped[str] = mapped_column(String(64), nullable=False)
    storage_ref: Mapped[str] = mapped_column(String(512), nullable=False)
    payload_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    payload_size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    frozen: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_by_intent_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("canonical_intents.id", ondelete="SET NULL"),
        nullable=True,
    )
    recorded_by_job_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("canonical_jobs.id", ondelete="SET NULL"),
        nullable=True,
    )
    created_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)


class ExternalNormalizedSnapshot(FinancialBase):
    __tablename__ = "external_normalized_snapshots"
    __table_args__ = (
        UniqueConstraint("tenant_id", "snapshot_token", name="uq_external_normalized_snapshots_token"),
        Index("idx_external_normalized_snapshots_run", "tenant_id", "sync_run_id", "created_at"),
    )

    entity_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("cp_entities.id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
        comment="Entity scope for multi-entity tenants",
    )
    sync_run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("external_sync_runs.id", ondelete="RESTRICT"), nullable=False
    )
    dataset_type: Mapped[str] = mapped_column(String(128), nullable=False)
    snapshot_token: Mapped[str] = mapped_column(String(64), nullable=False)
    storage_ref: Mapped[str] = mapped_column(String(512), nullable=False)
    canonical_payload_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    frozen: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)


class ExternalMappingDefinition(FinancialBase):
    __tablename__ = "external_mapping_definitions"
    __table_args__ = (
        UniqueConstraint("tenant_id", "organisation_id", "mapping_code", name="uq_external_mapping_definitions_code"),
        CheckConstraint("mapping_status IN ('draft','active','retired')", name="ck_external_mapping_definitions_status"),
        Index("idx_external_mapping_definitions_lookup", "tenant_id", "organisation_id", "mapping_status", "created_at"),
    )

    entity_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("cp_entities.id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
        comment="Entity scope for multi-entity tenants",
    )
    organisation_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    mapping_code: Mapped[str] = mapped_column(String(128), nullable=False)
    mapping_name: Mapped[str] = mapped_column(String(255), nullable=False)
    dataset_type: Mapped[str] = mapped_column(String(128), nullable=False)
    mapping_status: Mapped[str] = mapped_column(String(32), nullable=False, default="draft")
    created_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)


class ErpAccountExternalRef(Base):
    __tablename__ = "erp_account_external_refs"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "mapping_id",
            "connector_type",
            "external_account_id",
            name="uq_erp_account_ref_per_connector",
        ),
        Index("ix_erp_account_external_refs_tenant", "tenant_id"),
        Index("ix_erp_account_external_refs_mapping", "mapping_id"),
        Index("ix_erp_account_external_refs_connector", "tenant_id", "connector_type"),
        Index(
            "ix_erp_account_external_refs_stale",
            "tenant_id",
            "is_stale",
            postgresql_where=text("is_stale = true"),
        ),
        Index(
            "ix_erp_account_external_refs_internal_code",
            "tenant_id",
            "connector_type",
            "internal_account_code",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    mapping_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("external_mapping_definitions.id", ondelete="RESTRICT"),
        nullable=False,
    )
    connector_type: Mapped[str] = mapped_column(String(32), nullable=False)
    external_account_id: Mapped[str] = mapped_column(String(256), nullable=False)
    external_account_code: Mapped[str | None] = mapped_column(String(128), nullable=True)
    external_account_name: Mapped[str | None] = mapped_column(String(256), nullable=True)
    internal_account_code: Mapped[str] = mapped_column(String(32), nullable=False)
    last_synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    source_version_token: Mapped[str | None] = mapped_column(String(256), nullable=True)
    is_stale: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    stale_detected_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("now()"),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("now()"),
    )
    chain_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    previous_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)


class ExternalMappingVersion(FinancialBase):
    __tablename__ = "external_mapping_versions"
    __table_args__ = (
        UniqueConstraint("tenant_id", "mapping_definition_id", "version_no", name="uq_external_mapping_versions_no"),
        CheckConstraint(_STATUS_CHECK, name="ck_external_mapping_versions_status"),
        Index("idx_external_mapping_versions_lookup", "tenant_id", "mapping_definition_id", "version_no", "created_at"),
    )

    entity_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("cp_entities.id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
        comment="Entity scope for multi-entity tenants",
    )
    mapping_definition_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("external_mapping_definitions.id", ondelete="RESTRICT"),
        nullable=False,
    )
    version_no: Mapped[int] = mapped_column(Integer, nullable=False)
    version_token: Mapped[str] = mapped_column(String(64), nullable=False)
    mapping_payload_json: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    supersedes_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("external_mapping_versions.id", ondelete="RESTRICT"),
        nullable=True,
    )
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="candidate")
    created_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)


class ExternalSyncEvidenceLink(FinancialBase):
    __tablename__ = "external_sync_evidence_links"
    __table_args__ = (
        Index("idx_external_sync_evidence_links_run", "tenant_id", "sync_run_id", "created_at"),
    )

    entity_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("cp_entities.id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
        comment="Entity scope for multi-entity tenants",
    )
    sync_run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("external_sync_runs.id", ondelete="RESTRICT"), nullable=False
    )
    evidence_type: Mapped[str] = mapped_column(String(64), nullable=False)
    evidence_ref: Mapped[str] = mapped_column(Text, nullable=False)
    evidence_label: Mapped[str] = mapped_column(String(255), nullable=False)
    evidence_payload_json: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    created_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)


class ExternalSyncError(FinancialBase):
    __tablename__ = "external_sync_errors"
    __table_args__ = (
        CheckConstraint("severity IN ('info','warning','error','critical')", name="ck_external_sync_errors_severity"),
        Index("idx_external_sync_errors_run", "tenant_id", "sync_run_id", "created_at"),
    )

    entity_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("cp_entities.id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
        comment="Entity scope for multi-entity tenants",
    )
    sync_run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("external_sync_runs.id", ondelete="RESTRICT"), nullable=False
    )
    error_code: Mapped[str] = mapped_column(String(128), nullable=False)
    severity: Mapped[str] = mapped_column(String(16), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    details_json: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    created_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)


class ExternalSyncPublishEvent(FinancialBase):
    __tablename__ = "external_sync_publish_events"
    __table_args__ = (
        UniqueConstraint("tenant_id", "sync_run_id", "idempotency_key", name="uq_external_sync_publish_events_idempotency"),
        CheckConstraint("event_status IN ('pending','approved','rejected')", name="ck_external_sync_publish_events_status"),
        Index("idx_external_sync_publish_events_lookup", "tenant_id", "sync_run_id", "created_at"),
    )

    entity_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("cp_entities.id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
        comment="Entity scope for multi-entity tenants",
    )
    sync_run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("external_sync_runs.id", ondelete="RESTRICT"), nullable=False
    )
    idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False)
    event_status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending")
    approved_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    rejection_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)


class ExternalConnectorCapabilityRegistry(FinancialBase):
    __tablename__ = "external_connector_capability_registry"
    __table_args__ = (
        UniqueConstraint("tenant_id", "connector_type", "dataset_type", name="uq_external_connector_capability_registry"),
        Index("idx_external_connector_capability_registry_lookup", "tenant_id", "connector_type", "dataset_type"),
    )

    connector_type: Mapped[str] = mapped_column(String(64), nullable=False)
    dataset_type: Mapped[str] = mapped_column(String(128), nullable=False)
    supports_full_sync: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    supports_incremental_sync: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    supports_resumable_extraction: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)


class ExternalConnectorVersionRegistry(FinancialBase):
    __tablename__ = "external_connector_version_registry"
    __table_args__ = (
        UniqueConstraint("tenant_id", "connector_type", "version", name="uq_external_connector_version_registry"),
        CheckConstraint(_STATUS_CHECK, name="ck_external_connector_version_registry_status"),
        Index("idx_external_connector_version_registry_lookup", "tenant_id", "connector_type", "status", "created_at"),
    )

    connector_type: Mapped[str] = mapped_column(String(64), nullable=False)
    version: Mapped[str] = mapped_column(String(64), nullable=False)
    checksum: Mapped[str] = mapped_column(String(64), nullable=False)
    release_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="active")
    deprecation_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    created_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)


class ExternalPeriodLock(FinancialBase):
    __tablename__ = "external_period_locks"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "organisation_id",
            "entity_id",
            "dataset_type",
            "period_key",
            name="uq_external_period_locks_scope_period",
        ),
        CheckConstraint("lock_status IN ('locked','superseded')", name="ck_external_period_locks_status"),
        Index("idx_external_period_locks_lookup", "tenant_id", "organisation_id", "dataset_type", "period_key"),
    )

    organisation_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    entity_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    dataset_type: Mapped[str] = mapped_column(String(128), nullable=False)
    period_key: Mapped[str] = mapped_column(String(64), nullable=False)
    lock_status: Mapped[str] = mapped_column(String(32), nullable=False, default="locked")
    lock_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_sync_run_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("external_sync_runs.id", ondelete="RESTRICT"), nullable=True
    )
    supersedes_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("external_period_locks.id", ondelete="RESTRICT"), nullable=True
    )
    created_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)


class ExternalBackdatedModificationAlert(FinancialBase):
    __tablename__ = "external_backdated_modification_alerts"
    __table_args__ = (
        CheckConstraint("severity IN ('minor','significant','critical')", name="ck_external_backdated_modification_alerts_severity"),
        CheckConstraint("alert_status IN ('open','acknowledged','closed')", name="ck_external_backdated_modification_alerts_status"),
        Index("idx_external_backdated_modification_alerts_lookup", "tenant_id", "sync_run_id", "created_at"),
    )

    sync_run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("external_sync_runs.id", ondelete="RESTRICT"), nullable=False
    )
    period_lock_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("external_period_locks.id", ondelete="RESTRICT"), nullable=False
    )
    severity: Mapped[str] = mapped_column(String(16), nullable=False)
    alert_status: Mapped[str] = mapped_column(String(16), nullable=False, default="open")
    message: Mapped[str] = mapped_column(Text, nullable=False)
    details_json: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    acknowledged_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    acknowledged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)


class ExternalSyncDriftReport(FinancialBase):
    __tablename__ = "external_sync_drift_reports"
    __table_args__ = (
        UniqueConstraint("tenant_id", "sync_run_id", name="uq_external_sync_drift_reports_run"),
        CheckConstraint("drift_severity IN ('none','minor','significant','critical')", name="ck_external_sync_drift_reports_severity"),
        Index("idx_external_sync_drift_reports_lookup", "tenant_id", "sync_run_id", "created_at"),
    )

    sync_run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("external_sync_runs.id", ondelete="RESTRICT"), nullable=False
    )
    drift_detected: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    drift_severity: Mapped[str] = mapped_column(String(16), nullable=False, default="none")
    total_variances: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    metrics_checked_json: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, nullable=False, default=list)
    generated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)


class ExternalSyncHealthAlert(FinancialBase):
    __tablename__ = "external_sync_health_alerts"
    __table_args__ = (
        CheckConstraint(
            "alert_type IN ('scheduled_sync_missed','consecutive_failure_threshold','data_staleness','connection_dead')",
            name="ck_external_sync_health_alerts_type",
        ),
        CheckConstraint("alert_status IN ('open','acknowledged','resolved')", name="ck_external_sync_health_alerts_status"),
        Index("idx_external_sync_health_alerts_lookup", "tenant_id", "connection_id", "alert_status", "created_at"),
    )

    connection_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("external_connections.id", ondelete="RESTRICT"), nullable=False
    )
    sync_run_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("external_sync_runs.id", ondelete="RESTRICT"), nullable=True
    )
    dataset_type: Mapped[str | None] = mapped_column(String(128), nullable=True)
    alert_type: Mapped[str] = mapped_column(String(64), nullable=False)
    alert_status: Mapped[str] = mapped_column(String(16), nullable=False, default="open")
    message: Mapped[str] = mapped_column(Text, nullable=False)
    payload_json: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    created_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)


class ExternalDataConsentLog(FinancialBase):
    __tablename__ = "external_data_consent_logs"
    __table_args__ = (
        CheckConstraint("consent_action IN ('captured','validated','expired')", name="ck_external_data_consent_logs_action"),
        Index("idx_external_data_consent_logs_lookup", "tenant_id", "connection_id", "created_at"),
    )

    connection_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("external_connections.id", ondelete="RESTRICT"), nullable=False
    )
    sync_run_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("external_sync_runs.id", ondelete="RESTRICT"), nullable=True
    )
    consent_reference: Mapped[str] = mapped_column(String(255), nullable=False)
    consent_action: Mapped[str] = mapped_column(String(32), nullable=False)
    consent_payload_json: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    created_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)


class ExternalSyncSLAConfig(FinancialBase):
    __tablename__ = "external_sync_sla_configs"
    __table_args__ = (
        UniqueConstraint("tenant_id", "organisation_id", "connection_id", "dataset_type", name="uq_external_sync_sla_configs_scope"),
        CheckConstraint("sla_hours > 0", name="ck_external_sync_sla_configs_sla_hours_positive"),
        Index("idx_external_sync_sla_configs_lookup", "tenant_id", "organisation_id", "dataset_type"),
    )

    organisation_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    connection_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("external_connections.id", ondelete="RESTRICT"), nullable=False
    )
    dataset_type: Mapped[str] = mapped_column(String(128), nullable=False)
    sla_hours: Mapped[int] = mapped_column(Integer, nullable=False)
    consecutive_failure_threshold: Mapped[int] = mapped_column(Integer, nullable=False, default=3)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
