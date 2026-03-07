from __future__ import annotations

import uuid
from decimal import Decimal
from typing import Any

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
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from financeops.db.base import FinancialBase


class NormalizationSource(FinancialBase):
    __tablename__ = "normalization_sources"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id", "source_code", name="uq_normalization_sources_tenant_code"
        ),
        CheckConstraint(
            "status IN ('active','inactive','archived')",
            name="ck_normalization_sources_status",
        ),
        Index("idx_normalization_sources_tenant", "tenant_id", "created_at"),
        Index("idx_normalization_sources_family_code", "tenant_id", "source_family", "source_code"),
    )

    organisation_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    source_family: Mapped[str] = mapped_column(String(64), nullable=False)
    source_code: Mapped[str] = mapped_column(String(128), nullable=False)
    source_name: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="active")
    created_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)


class NormalizationSourceVersion(FinancialBase):
    __tablename__ = "normalization_source_versions"
    __table_args__ = (
        UniqueConstraint(
            "source_id", "version_no", name="uq_normalization_source_versions_source_no"
        ),
        UniqueConstraint(
            "source_id",
            "version_token",
            name="uq_normalization_source_versions_source_token",
        ),
        CheckConstraint(
            "status IN ('candidate','active','superseded','rejected')",
            name="ck_normalization_source_versions_status",
        ),
        Index(
            "idx_normalization_source_versions_source",
            "tenant_id",
            "source_id",
            "created_at",
        ),
        Index(
            "uq_normalization_source_versions_one_active",
            "source_id",
            unique=True,
            postgresql_where=text("status = 'active'"),
        ),
    )

    source_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("normalization_sources.id", ondelete="RESTRICT"),
        nullable=False,
    )
    version_no: Mapped[int] = mapped_column(Integer, nullable=False)
    version_token: Mapped[str] = mapped_column(String(64), nullable=False)
    structure_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    header_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    row_signature_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    source_detection_summary_json: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, default=dict
    )
    supersedes_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("normalization_source_versions.id", ondelete="RESTRICT"),
        nullable=True,
    )
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="candidate")
    created_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)


class NormalizationMapping(FinancialBase):
    __tablename__ = "normalization_mappings"
    __table_args__ = (
        CheckConstraint(
            "mapping_type IN ('payroll_dimension','payroll_metric','gl_dimension','gl_metric')",
            name="ck_normalization_mappings_type",
        ),
        CheckConstraint(
            "confidence_score >= 0 AND confidence_score <= 1",
            name="ck_normalization_mappings_confidence",
        ),
        Index(
            "idx_normalization_mappings_source_version",
            "tenant_id",
            "source_version_id",
            "mapping_type",
        ),
        Index(
            "idx_normalization_mappings_field",
            "tenant_id",
            "source_version_id",
            "canonical_field_name",
        ),
    )

    source_version_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("normalization_source_versions.id", ondelete="CASCADE"),
        nullable=False,
    )
    mapping_type: Mapped[str] = mapped_column(String(32), nullable=False)
    source_field_name: Mapped[str] = mapped_column(String(255), nullable=False)
    canonical_field_name: Mapped[str] = mapped_column(String(128), nullable=False)
    transform_rule: Mapped[str | None] = mapped_column(String(64), nullable=True)
    default_value_json: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, default=dict
    )
    required_flag: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    confidence_score: Mapped[Decimal] = mapped_column(Numeric(5, 4), nullable=False)
    created_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)


class NormalizationRun(FinancialBase):
    __tablename__ = "normalization_runs"
    __table_args__ = (
        UniqueConstraint("tenant_id", "run_token", name="uq_normalization_runs_tenant_token"),
        CheckConstraint(
            "run_type IN ('payroll_normalization','gl_normalization')",
            name="ck_normalization_runs_type",
        ),
        CheckConstraint(
            "run_status IN ('pending','validated','finalized','failed')",
            name="ck_normalization_runs_status",
        ),
        Index(
            "idx_normalization_runs_source_period",
            "tenant_id",
            "source_id",
            "reporting_period",
        ),
        Index("idx_normalization_runs_token", "tenant_id", "run_token", unique=True),
    )

    organisation_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    source_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("normalization_sources.id", ondelete="RESTRICT"),
        nullable=False,
    )
    source_version_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("normalization_source_versions.id", ondelete="RESTRICT"),
        nullable=False,
    )
    mapping_version_token: Mapped[str] = mapped_column(String(64), nullable=False)
    run_type: Mapped[str] = mapped_column(String(64), nullable=False)
    reporting_period: Mapped[Any] = mapped_column(Date, nullable=False)
    source_artifact_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    source_file_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    run_token: Mapped[str] = mapped_column(String(64), nullable=False)
    run_status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending")
    validation_summary_json: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, default=dict
    )
    created_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)


class PayrollNormalizedLine(FinancialBase):
    __tablename__ = "payroll_normalized_lines"
    __table_args__ = (
        UniqueConstraint(
            "run_id",
            "row_no",
            "employee_code",
            "canonical_metric_code",
            name="uq_payroll_normalized_lines_row_metric",
        ),
        CheckConstraint(
            "normalization_status IN ('valid','warning','invalid')",
            name="ck_payroll_normalized_lines_status",
        ),
        Index("idx_payroll_normalized_lines_run", "tenant_id", "run_id", "row_no"),
        Index(
            "idx_payroll_normalized_lines_employee_period",
            "tenant_id",
            "employee_code",
            "payroll_period",
        ),
        Index(
            "idx_payroll_normalized_lines_metric",
            "tenant_id",
            "canonical_metric_code",
            "payroll_period",
        ),
    )

    run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("normalization_runs.id", ondelete="CASCADE"),
        nullable=False,
    )
    row_no: Mapped[int] = mapped_column(Integer, nullable=False)
    employee_code: Mapped[str | None] = mapped_column(String(128), nullable=True)
    employee_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    payroll_period: Mapped[Any] = mapped_column(Date, nullable=False)
    legal_entity: Mapped[str | None] = mapped_column(String(255), nullable=True)
    department: Mapped[str | None] = mapped_column(String(255), nullable=True)
    cost_center: Mapped[str | None] = mapped_column(String(255), nullable=True)
    business_unit: Mapped[str | None] = mapped_column(String(255), nullable=True)
    location: Mapped[str | None] = mapped_column(String(255), nullable=True)
    grade: Mapped[str | None] = mapped_column(String(128), nullable=True)
    designation: Mapped[str | None] = mapped_column(String(255), nullable=True)
    currency_code: Mapped[str] = mapped_column(String(3), nullable=False)
    canonical_metric_code: Mapped[str] = mapped_column(String(128), nullable=False)
    amount_value: Mapped[Decimal] = mapped_column(Numeric(20, 6), nullable=False)
    source_row_ref: Mapped[str] = mapped_column(String(128), nullable=False)
    source_column_ref: Mapped[str] = mapped_column(String(128), nullable=False)
    normalization_status: Mapped[str] = mapped_column(String(16), nullable=False)
    created_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)


class GlNormalizedLine(FinancialBase):
    __tablename__ = "gl_normalized_lines"
    __table_args__ = (
        UniqueConstraint("run_id", "row_no", name="uq_gl_normalized_lines_run_row"),
        CheckConstraint(
            "normalization_status IN ('valid','warning','invalid')",
            name="ck_gl_normalized_lines_status",
        ),
        Index("idx_gl_normalized_lines_run", "tenant_id", "run_id", "row_no"),
        Index(
            "idx_gl_normalized_lines_account_period",
            "tenant_id",
            "account_code",
            "posting_period",
        ),
    )

    run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("normalization_runs.id", ondelete="CASCADE"),
        nullable=False,
    )
    row_no: Mapped[int] = mapped_column(Integer, nullable=False)
    journal_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    journal_line_no: Mapped[str | None] = mapped_column(String(64), nullable=True)
    posting_date: Mapped[Any | None] = mapped_column(Date, nullable=True)
    document_date: Mapped[Any | None] = mapped_column(Date, nullable=True)
    posting_period: Mapped[str] = mapped_column(String(16), nullable=False)
    legal_entity: Mapped[str | None] = mapped_column(String(255), nullable=True)
    account_code: Mapped[str | None] = mapped_column(String(128), nullable=True)
    account_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    cost_center: Mapped[str | None] = mapped_column(String(255), nullable=True)
    department: Mapped[str | None] = mapped_column(String(255), nullable=True)
    business_unit: Mapped[str | None] = mapped_column(String(255), nullable=True)
    project: Mapped[str | None] = mapped_column(String(255), nullable=True)
    customer: Mapped[str | None] = mapped_column(String(255), nullable=True)
    vendor: Mapped[str | None] = mapped_column(String(255), nullable=True)
    source_module: Mapped[str | None] = mapped_column(String(128), nullable=True)
    source_document_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    currency_code: Mapped[str] = mapped_column(String(3), nullable=False)
    debit_amount: Mapped[Decimal] = mapped_column(Numeric(20, 6), nullable=False)
    credit_amount: Mapped[Decimal] = mapped_column(Numeric(20, 6), nullable=False)
    signed_amount: Mapped[Decimal] = mapped_column(Numeric(20, 6), nullable=False)
    local_amount: Mapped[Decimal] = mapped_column(Numeric(20, 6), nullable=False)
    transaction_amount: Mapped[Decimal] = mapped_column(Numeric(20, 6), nullable=False)
    source_row_ref: Mapped[str] = mapped_column(String(128), nullable=False)
    source_column_ref: Mapped[str] = mapped_column(String(128), nullable=False)
    normalization_status: Mapped[str] = mapped_column(String(16), nullable=False)
    created_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)


class NormalizationException(FinancialBase):
    __tablename__ = "normalization_exceptions"
    __table_args__ = (
        CheckConstraint(
            "severity IN ('info','warning','error')",
            name="ck_normalization_exceptions_severity",
        ),
        CheckConstraint(
            "resolution_status IN ('open','acknowledged','resolved')",
            name="ck_normalization_exceptions_resolution_status",
        ),
        Index("idx_normalization_exceptions_run", "tenant_id", "run_id", "created_at"),
        Index(
            "idx_normalization_exceptions_severity", "tenant_id", "run_id", "severity"
        ),
    )

    run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("normalization_runs.id", ondelete="CASCADE"),
        nullable=False,
    )
    exception_code: Mapped[str] = mapped_column(String(64), nullable=False)
    severity: Mapped[str] = mapped_column(String(16), nullable=False)
    source_ref: Mapped[str] = mapped_column(String(255), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    resolution_status: Mapped[str] = mapped_column(String(24), nullable=False, default="open")
    created_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)


class NormalizationEvidenceLink(FinancialBase):
    __tablename__ = "normalization_evidence_links"
    __table_args__ = (
        CheckConstraint(
            "normalized_line_type IN ('payroll_line','gl_line')",
            name="ck_normalization_evidence_links_line_type",
        ),
        CheckConstraint(
            "evidence_type IN ('source_row','source_file','raw_payload_block','import_artifact')",
            name="ck_normalization_evidence_links_evidence_type",
        ),
        Index(
            "idx_normalization_evidence_links_run_line",
            "tenant_id",
            "run_id",
            "normalized_line_id",
        ),
        Index(
            "idx_normalization_evidence_links_run",
            "tenant_id",
            "run_id",
            "created_at",
        ),
    )

    run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("normalization_runs.id", ondelete="CASCADE"),
        nullable=False,
    )
    normalized_line_type: Mapped[str] = mapped_column(String(32), nullable=False)
    normalized_line_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    evidence_type: Mapped[str] = mapped_column(String(64), nullable=False)
    evidence_ref: Mapped[str] = mapped_column(Text, nullable=False)
    evidence_label: Mapped[str] = mapped_column(String(255), nullable=False)
    created_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
