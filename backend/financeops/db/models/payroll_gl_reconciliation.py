from __future__ import annotations

import uuid
from datetime import date
from typing import Any

from sqlalchemy import (
    CheckConstraint,
    Date,
    ForeignKey,
    Index,
    String,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from financeops.db.base import FinancialBase


class PayrollGlReconciliationMapping(FinancialBase):
    __tablename__ = "payroll_gl_reconciliation_mappings"
    __table_args__ = (
        CheckConstraint(
            "status IN ('candidate','active','superseded','rejected')",
            name="ck_payroll_gl_recon_mappings_status",
        ),
        Index(
            "idx_payroll_gl_recon_mappings_lookup",
            "tenant_id",
            "organisation_id",
            "mapping_code",
            "created_at",
        ),
        Index(
            "uq_payroll_gl_recon_mappings_one_active",
            "tenant_id",
            "organisation_id",
            "mapping_code",
            unique=True,
            postgresql_where=text("status = 'active'"),
        ),
    )

    organisation_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    mapping_code: Mapped[str] = mapped_column(String(64), nullable=False)
    mapping_name: Mapped[str] = mapped_column(String(255), nullable=False)
    payroll_metric_code: Mapped[str] = mapped_column(String(128), nullable=False)
    gl_account_selector_json: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, default=dict
    )
    cost_center_rule_json: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, default=dict
    )
    department_rule_json: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, default=dict
    )
    entity_rule_json: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, default=dict
    )
    effective_from: Mapped[date] = mapped_column(Date, nullable=False)
    supersedes_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("payroll_gl_reconciliation_mappings.id", ondelete="RESTRICT"),
        nullable=True,
    )
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="candidate")
    created_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)


class PayrollGlReconciliationRule(FinancialBase):
    __tablename__ = "payroll_gl_reconciliation_rules"
    __table_args__ = (
        CheckConstraint(
            "rule_type IN ("
            "'aggregate_tie_rule','component_tie_rule','timing_rule',"
            "'contribution_rule','payable_rule','cost_center_rule'"
            ")",
            name="ck_payroll_gl_recon_rules_type",
        ),
        CheckConstraint(
            "status IN ('candidate','active','superseded','rejected')",
            name="ck_payroll_gl_recon_rules_status",
        ),
        Index(
            "idx_payroll_gl_recon_rules_lookup",
            "tenant_id",
            "organisation_id",
            "rule_code",
            "created_at",
        ),
        Index(
            "uq_payroll_gl_recon_rules_one_active",
            "tenant_id",
            "organisation_id",
            "rule_code",
            unique=True,
            postgresql_where=text("status = 'active'"),
        ),
    )

    organisation_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    rule_code: Mapped[str] = mapped_column(String(64), nullable=False)
    rule_name: Mapped[str] = mapped_column(String(255), nullable=False)
    rule_type: Mapped[str] = mapped_column(String(64), nullable=False)
    tolerance_json: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, default=dict
    )
    materiality_json: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, default=dict
    )
    timing_window_json: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, default=dict
    )
    classification_behavior_json: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, default=dict
    )
    effective_from: Mapped[date] = mapped_column(Date, nullable=False)
    supersedes_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("payroll_gl_reconciliation_rules.id", ondelete="RESTRICT"),
        nullable=True,
    )
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="candidate")
    created_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)


class PayrollGlReconciliationRun(FinancialBase):
    __tablename__ = "payroll_gl_reconciliation_runs"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "run_token",
            name="uq_payroll_gl_recon_runs_tenant_token",
        ),
        CheckConstraint(
            "status IN ('created','running','completed','failed')",
            name="ck_payroll_gl_recon_runs_status",
        ),
        Index(
            "idx_payroll_gl_recon_runs_lookup",
            "tenant_id",
            "organisation_id",
            "reporting_period",
            "created_at",
        ),
        Index(
            "idx_payroll_gl_recon_runs_session",
            "tenant_id",
            "reconciliation_session_id",
        ),
    )

    organisation_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    reconciliation_session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("reconciliation_sessions.id", ondelete="RESTRICT"),
        nullable=False,
    )
    payroll_run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("normalization_runs.id", ondelete="RESTRICT"),
        nullable=False,
    )
    gl_run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("normalization_runs.id", ondelete="RESTRICT"),
        nullable=False,
    )
    mapping_version_token: Mapped[str] = mapped_column(String(64), nullable=False)
    rule_version_token: Mapped[str] = mapped_column(String(64), nullable=False)
    reporting_period: Mapped[date] = mapped_column(Date, nullable=False)
    run_token: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="created")
    created_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)


class PayrollGlReconciliationRunScope(FinancialBase):
    __tablename__ = "payroll_gl_reconciliation_run_scopes"
    __table_args__ = (
        UniqueConstraint(
            "payroll_gl_reconciliation_run_id",
            "scope_code",
            name="uq_payroll_gl_recon_run_scopes_code",
        ),
        Index(
            "idx_payroll_gl_recon_run_scopes_run",
            "tenant_id",
            "payroll_gl_reconciliation_run_id",
        ),
    )

    payroll_gl_reconciliation_run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("payroll_gl_reconciliation_runs.id", ondelete="CASCADE"),
        nullable=False,
    )
    scope_code: Mapped[str] = mapped_column(String(64), nullable=False)
    scope_label: Mapped[str] = mapped_column(String(255), nullable=False)
    scope_json: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    created_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
