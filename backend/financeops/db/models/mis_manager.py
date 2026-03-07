from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKeyConstraint,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from financeops.db.base import FinancialBase


class MisTemplate(FinancialBase):
    __tablename__ = "mis_templates"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id", "template_code", name="uq_mis_templates_tenant_template_code"
        ),
        CheckConstraint(
            "status IN ('active', 'inactive', 'archived')",
            name="ck_mis_templates_status",
        ),
        Index("idx_mis_templates_tenant_created", "tenant_id", "created_at"),
        Index("idx_mis_templates_entity", "tenant_id", "entity_name"),
        Index("idx_mis_templates_template_code", "tenant_id", "template_code"),
    )

    # Legacy fields retained for compatibility with pre-Phase-1F.1 service/tests.
    name: Mapped[str] = mapped_column(
        String(255), nullable=False, default="legacy_template"
    )
    entity_name: Mapped[str] = mapped_column(
        String(255), nullable=False, default="legacy_entity"
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    is_master: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    template_data: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, default=dict
    )
    sheet_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # Phase 1F.1 canonical fields.
    organisation_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    template_code: Mapped[str] = mapped_column(String(128), nullable=False)
    template_name: Mapped[str] = mapped_column(String(255), nullable=False)
    template_type: Mapped[str] = mapped_column(
        String(64), nullable=False, default="custom"
    )
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="active")
    created_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)


class MisUpload(FinancialBase):
    """Legacy upload table retained for backward compatibility."""

    __tablename__ = "mis_uploads"
    __table_args__ = (
        Index("idx_mis_uploads_tenant_created", "tenant_id", "created_at"),
        Index("idx_mis_uploads_period", "tenant_id", "period_year", "period_month"),
    )

    template_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("mis_templates.id"), nullable=True
    )
    entity_name: Mapped[str] = mapped_column(String(255), nullable=False)
    period_year: Mapped[int] = mapped_column(Integer, nullable=False)
    period_month: Mapped[int] = mapped_column(Integer, nullable=False)
    file_name: Mapped[str] = mapped_column(String(500), nullable=False)
    file_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="pending")
    upload_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    parsed_data: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    uploaded_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)


class MisTemplateVersion(FinancialBase):
    __tablename__ = "mis_template_versions"
    __table_args__ = (
        UniqueConstraint(
            "template_id",
            "version_no",
            name="uq_mis_template_versions_template_version_no",
        ),
        UniqueConstraint(
            "template_id",
            "version_token",
            name="uq_mis_template_versions_template_version_token",
        ),
        CheckConstraint(
            "status IN ('candidate', 'active', 'superseded', 'rejected')",
            name="ck_mis_template_versions_status",
        ),
        Index(
            "idx_mis_template_versions_template_created",
            "tenant_id",
            "template_id",
            "created_at",
        ),
        Index(
            "uq_mis_template_versions_one_active",
            "template_id",
            unique=True,
            postgresql_where=text("status = 'active'"),
        ),
    )

    template_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("mis_templates.id", ondelete="RESTRICT"),
        nullable=False,
    )
    version_no: Mapped[int] = mapped_column(Integer, nullable=False)
    version_token: Mapped[str] = mapped_column(String(64), nullable=False)
    based_on_version_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("mis_template_versions.id", ondelete="RESTRICT"),
        nullable=True,
    )
    supersedes_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("mis_template_versions.id", ondelete="RESTRICT"),
        nullable=True,
    )
    structure_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    header_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    row_signature_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    column_signature_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    detection_summary_json: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, default=dict
    )
    drift_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="candidate")
    effective_from: Mapped[Any | None] = mapped_column(Date, nullable=True)
    created_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)


class MisTemplateSection(FinancialBase):
    __tablename__ = "mis_template_sections"
    __table_args__ = (
        UniqueConstraint(
            "template_version_id", "section_code", name="uq_mis_template_sections_code"
        ),
        UniqueConstraint(
            "template_version_id",
            "section_order",
            name="uq_mis_template_sections_order",
        ),
        Index("idx_mis_template_sections_version", "tenant_id", "template_version_id"),
    )

    template_version_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("mis_template_versions.id", ondelete="CASCADE"),
        nullable=False,
    )
    section_code: Mapped[str] = mapped_column(String(64), nullable=False)
    section_name: Mapped[str] = mapped_column(String(255), nullable=False)
    section_order: Mapped[int] = mapped_column(Integer, nullable=False)
    start_row_signature: Mapped[str] = mapped_column(String(128), nullable=False)
    end_row_signature: Mapped[str] = mapped_column(String(128), nullable=False)
    created_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)


class MisTemplateColumn(FinancialBase):
    __tablename__ = "mis_template_columns"
    __table_args__ = (
        UniqueConstraint(
            "template_version_id",
            "ordinal_position",
            name="uq_mis_template_columns_ordinal",
        ),
        CheckConstraint(
            "column_role IN "
            "('period','metric_name','value','dimension','subtotal_flag','formula_flag','notes')",
            name="ck_mis_template_columns_role",
        ),
        CheckConstraint(
            "data_type IN ('string','numeric','date','boolean','json')",
            name="ck_mis_template_columns_data_type",
        ),
        Index("idx_mis_template_columns_version", "tenant_id", "template_version_id"),
    )

    template_version_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("mis_template_versions.id", ondelete="CASCADE"),
        nullable=False,
    )
    source_column_label: Mapped[str] = mapped_column(Text, nullable=False)
    normalized_column_label: Mapped[str] = mapped_column(Text, nullable=False)
    column_role: Mapped[str] = mapped_column(String(32), nullable=False)
    data_type: Mapped[str] = mapped_column(String(32), nullable=False, default="string")
    ordinal_position: Mapped[int] = mapped_column(Integer, nullable=False)
    canonical_dimension_code: Mapped[str | None] = mapped_column(
        String(64), nullable=True
    )
    canonical_metric_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    is_required: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_period_column: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )
    is_value_column: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )
    created_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)


class MisTemplateRowMapping(FinancialBase):
    __tablename__ = "mis_template_row_mappings"
    __table_args__ = (
        CheckConstraint(
            "confidence_score >= 0 AND confidence_score <= 1",
            name="ck_mis_template_row_mappings_confidence",
        ),
        ForeignKeyConstraint(
            ["template_version_id", "section_code"],
            [
                "mis_template_sections.template_version_id",
                "mis_template_sections.section_code",
            ],
            ondelete="RESTRICT",
        ),
        Index(
            "idx_mis_template_row_mappings_version", "tenant_id", "template_version_id"
        ),
    )

    template_version_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("mis_template_versions.id", ondelete="CASCADE"),
        nullable=False,
    )
    source_row_pattern: Mapped[str] = mapped_column(Text, nullable=False)
    normalized_row_label: Mapped[str] = mapped_column(Text, nullable=False)
    canonical_metric_code: Mapped[str] = mapped_column(String(64), nullable=False)
    sign_rule: Mapped[str] = mapped_column(String(32), nullable=False)
    aggregation_rule: Mapped[str] = mapped_column(String(32), nullable=False)
    section_code: Mapped[str] = mapped_column(String(64), nullable=False)
    confidence_score: Mapped[Any] = mapped_column(Numeric(5, 4), nullable=False)
    created_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)


class MisDataSnapshot(FinancialBase):
    __tablename__ = "mis_data_snapshots"
    __table_args__ = (
        UniqueConstraint(
            "template_version_id",
            "snapshot_token",
            name="uq_mis_data_snapshots_version_token",
        ),
        CheckConstraint(
            "snapshot_status IN ('pending', 'validated', 'finalized', 'failed')",
            name="ck_mis_data_snapshots_status",
        ),
        Index(
            "idx_mis_data_snapshots_period",
            "tenant_id",
            "template_id",
            "reporting_period",
        ),
    )

    organisation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False
    )
    template_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("mis_templates.id", ondelete="RESTRICT"),
        nullable=False,
    )
    template_version_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("mis_template_versions.id", ondelete="RESTRICT"),
        nullable=False,
    )
    reporting_period: Mapped[Any] = mapped_column(Date, nullable=False)
    upload_artifact_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False
    )
    snapshot_token: Mapped[str] = mapped_column(String(64), nullable=False)
    source_file_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    sheet_name: Mapped[str] = mapped_column(String(255), nullable=False)
    snapshot_status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="pending"
    )
    validation_summary_json: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, default=dict
    )
    created_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)


class MisNormalizedLine(FinancialBase):
    __tablename__ = "mis_normalized_lines"
    __table_args__ = (
        UniqueConstraint(
            "snapshot_id", "line_no", name="uq_mis_normalized_lines_snapshot_line_no"
        ),
        CheckConstraint(
            "validation_status IN ('valid','warning','invalid')",
            name="ck_mis_normalized_lines_validation_status",
        ),
        Index(
            "idx_mis_normalized_lines_snapshot", "tenant_id", "snapshot_id", "line_no"
        ),
    )

    snapshot_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("mis_data_snapshots.id", ondelete="CASCADE"),
        nullable=False,
    )
    line_no: Mapped[int] = mapped_column(Integer, nullable=False)
    canonical_metric_code: Mapped[str] = mapped_column(String(64), nullable=False)
    canonical_dimension_json: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, default=dict
    )
    source_row_ref: Mapped[str] = mapped_column(Text, nullable=False)
    source_column_ref: Mapped[str] = mapped_column(Text, nullable=False)
    period_value: Mapped[Any] = mapped_column(Numeric(18, 6), nullable=False)
    currency_code: Mapped[str] = mapped_column(String(3), nullable=False)
    sign_applied: Mapped[str] = mapped_column(
        String(32), nullable=False, default="as_is"
    )
    validation_status: Mapped[str] = mapped_column(
        String(16), nullable=False, default="valid"
    )
    created_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)


class MisIngestionException(FinancialBase):
    __tablename__ = "mis_ingestion_exceptions"
    __table_args__ = (
        CheckConstraint(
            "severity IN ('info','warning','error')",
            name="ck_mis_ingestion_exceptions_severity",
        ),
        CheckConstraint(
            "resolution_status IN ('open','acknowledged','resolved')",
            name="ck_mis_ingestion_exceptions_resolution_status",
        ),
        Index(
            "idx_mis_ingestion_exceptions_snapshot",
            "tenant_id",
            "snapshot_id",
            "created_at",
        ),
    )

    snapshot_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("mis_data_snapshots.id", ondelete="CASCADE"),
        nullable=False,
    )
    exception_code: Mapped[str] = mapped_column(String(64), nullable=False)
    severity: Mapped[str] = mapped_column(String(16), nullable=False)
    source_ref: Mapped[str] = mapped_column(Text, nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    resolution_status: Mapped[str] = mapped_column(
        String(24), nullable=False, default="open"
    )
    created_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)


class MisDriftEvent(FinancialBase):
    __tablename__ = "mis_drift_events"
    __table_args__ = (
        CheckConstraint(
            "drift_type IN "
            "('HEADER_CHANGE','SECTION_REORDER','PERIOD_AXIS_CHANGE','DIMENSION_CHANGE','ROW_PATTERN_CHANGE','MAJOR_LAYOUT_CHANGE')",
            name="ck_mis_drift_events_type",
        ),
        CheckConstraint(
            "decision_status IN ('pending_review','accepted','rejected')",
            name="ck_mis_drift_events_decision_status",
        ),
        Index(
            "idx_mis_drift_events_template", "tenant_id", "template_id", "created_at"
        ),
    )

    template_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("mis_templates.id", ondelete="RESTRICT"),
        nullable=False,
    )
    prior_template_version_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("mis_template_versions.id", ondelete="RESTRICT"),
        nullable=False,
    )
    candidate_template_version_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("mis_template_versions.id", ondelete="RESTRICT"),
        nullable=False,
    )
    drift_type: Mapped[str] = mapped_column(String(64), nullable=False)
    drift_details_json: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, default=dict
    )
    decision_status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="pending_review"
    )
    decided_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )
    decided_at: Mapped[Any | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)


class MisCanonicalMetricDictionary(FinancialBase):
    __tablename__ = "mis_canonical_metric_dictionary"
    __table_args__ = (
        UniqueConstraint(
            "version_no",
            "metric_code",
            name="uq_mis_canonical_metric_dict_version_code",
        ),
        CheckConstraint(
            "status IN ('active','deprecated')",
            name="ck_mis_canonical_metric_dict_status",
        ),
        Index("idx_mis_canonical_metric_dict_code", "tenant_id", "metric_code"),
    )

    version_no: Mapped[int] = mapped_column(Integer, nullable=False)
    metric_code: Mapped[str] = mapped_column(String(64), nullable=False)
    display_name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="active")
    created_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)


class MisCanonicalDimensionDictionary(FinancialBase):
    __tablename__ = "mis_canonical_dimension_dictionary"
    __table_args__ = (
        UniqueConstraint(
            "version_no",
            "dimension_code",
            name="uq_mis_canonical_dimension_dict_version_code",
        ),
        CheckConstraint(
            "status IN ('active','deprecated')",
            name="ck_mis_canonical_dimension_dict_status",
        ),
        Index("idx_mis_canonical_dimension_dict_code", "tenant_id", "dimension_code"),
    )

    version_no: Mapped[int] = mapped_column(Integer, nullable=False)
    dimension_code: Mapped[str] = mapped_column(String(64), nullable=False)
    display_name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="active")
    created_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
