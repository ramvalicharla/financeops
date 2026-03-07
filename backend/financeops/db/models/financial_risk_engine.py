from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
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


class RiskDefinition(FinancialBase):
    __tablename__ = "risk_definitions"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "organisation_id",
            "risk_code",
            "version_token",
            name="uq_risk_definitions_version_token",
        ),
        CheckConstraint(
            "risk_domain IN ('profitability','liquidity','leverage','working_capital','cost_structure','payroll','confidence','reconciliation_dependency','board_critical')",
            name="ck_risk_definitions_domain",
        ),
        CheckConstraint(
            "status IN ('candidate','active','superseded','rejected')",
            name="ck_risk_definitions_status",
        ),
        Index(
            "idx_risk_definitions_lookup",
            "tenant_id",
            "organisation_id",
            "risk_code",
            "effective_from",
            "created_at",
        ),
        Index(
            "uq_risk_definitions_one_active",
            "tenant_id",
            "organisation_id",
            "risk_code",
            unique=True,
            postgresql_where=text("status = 'active'"),
        ),
    )

    organisation_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    risk_code: Mapped[str] = mapped_column(String(128), nullable=False)
    risk_name: Mapped[str] = mapped_column(String(255), nullable=False)
    risk_domain: Mapped[str] = mapped_column(String(64), nullable=False)
    signal_selector_json: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, default=dict
    )
    definition_json: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    version_token: Mapped[str] = mapped_column(String(64), nullable=False)
    effective_from: Mapped[date] = mapped_column(Date, nullable=False)
    effective_to: Mapped[date | None] = mapped_column(Date, nullable=True)
    supersedes_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("risk_definitions.id", ondelete="RESTRICT"),
        nullable=True,
    )
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="candidate")
    created_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)


class RiskDefinitionDependency(FinancialBase):
    __tablename__ = "risk_definition_dependencies"
    __table_args__ = (
        CheckConstraint(
            "dependency_type IN ('metric_result','variance_result','trend_result','reconciliation_exception','risk_result')",
            name="ck_risk_definition_dependencies_type",
        ),
        CheckConstraint(
            "propagation_factor >= 0 AND propagation_factor <= 10",
            name="ck_risk_definition_dependencies_propagation_factor",
        ),
        CheckConstraint(
            "cap_limit >= 0 AND cap_limit <= 10",
            name="ck_risk_definition_dependencies_cap_limit",
        ),
        Index(
            "idx_risk_definition_dependencies_risk",
            "tenant_id",
            "risk_definition_id",
            "dependency_type",
            "id",
        ),
        Index(
            "idx_risk_definition_dependencies_depends_on",
            "tenant_id",
            "depends_on_risk_definition_id",
        ),
    )

    risk_definition_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("risk_definitions.id", ondelete="RESTRICT"),
        nullable=False,
    )
    dependency_type: Mapped[str] = mapped_column(String(64), nullable=False)
    depends_on_risk_definition_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("risk_definitions.id", ondelete="RESTRICT"),
        nullable=True,
    )
    signal_reference_code: Mapped[str | None] = mapped_column(String(128), nullable=True)
    propagation_factor: Mapped[Decimal] = mapped_column(
        Numeric(12, 6), nullable=False, default=Decimal("1")
    )
    amplification_rule_json: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, default=dict
    )
    attenuation_rule_json: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, default=dict
    )
    cap_limit: Mapped[Decimal] = mapped_column(
        Numeric(12, 6), nullable=False, default=Decimal("1")
    )
    created_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)


class RiskWeightConfiguration(FinancialBase):
    __tablename__ = "risk_weight_configurations"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "organisation_id",
            "weight_code",
            "version_token",
            name="uq_risk_weight_configurations_version_token",
        ),
        CheckConstraint(
            "scope_type IN ('global','metric','entity','domain','board_critical')",
            name="ck_risk_weight_configurations_scope_type",
        ),
        CheckConstraint(
            "weight_value >= 0 AND weight_value <= 10",
            name="ck_risk_weight_configurations_weight_value",
        ),
        CheckConstraint(
            "status IN ('candidate','active','superseded','rejected')",
            name="ck_risk_weight_configurations_status",
        ),
        Index(
            "idx_risk_weight_configurations_lookup",
            "tenant_id",
            "organisation_id",
            "weight_code",
            "effective_from",
            "created_at",
        ),
        Index(
            "uq_risk_weight_configurations_one_active",
            "tenant_id",
            "organisation_id",
            "weight_code",
            unique=True,
            postgresql_where=text("status = 'active'"),
        ),
    )

    organisation_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    weight_code: Mapped[str] = mapped_column(String(128), nullable=False)
    risk_code: Mapped[str] = mapped_column(String(128), nullable=False)
    scope_type: Mapped[str] = mapped_column(String(32), nullable=False, default="global")
    scope_value: Mapped[str | None] = mapped_column(String(128), nullable=True)
    weight_value: Mapped[Decimal] = mapped_column(Numeric(12, 6), nullable=False)
    board_critical_override: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    configuration_json: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    version_token: Mapped[str] = mapped_column(String(64), nullable=False)
    effective_from: Mapped[date] = mapped_column(Date, nullable=False)
    supersedes_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("risk_weight_configurations.id", ondelete="RESTRICT"),
        nullable=True,
    )
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="candidate")
    created_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)


class RiskMaterialityRule(FinancialBase):
    __tablename__ = "risk_materiality_rules"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "organisation_id",
            "rule_code",
            "version_token",
            name="uq_risk_materiality_rules_version_token",
        ),
        CheckConstraint(
            "status IN ('candidate','active','superseded','rejected')",
            name="ck_risk_materiality_rules_status",
        ),
        Index(
            "idx_risk_materiality_rules_lookup",
            "tenant_id",
            "organisation_id",
            "rule_code",
            "effective_from",
            "created_at",
        ),
        Index(
            "uq_risk_materiality_rules_one_active",
            "tenant_id",
            "organisation_id",
            "rule_code",
            unique=True,
            postgresql_where=text("status = 'active'"),
        ),
    )

    organisation_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    rule_code: Mapped[str] = mapped_column(String(128), nullable=False)
    rule_name: Mapped[str] = mapped_column(String(255), nullable=False)
    threshold_json: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    severity_mapping_json: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, default=dict
    )
    propagation_behavior_json: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, default=dict
    )
    escalation_rule_json: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, default=dict
    )
    version_token: Mapped[str] = mapped_column(String(64), nullable=False)
    effective_from: Mapped[date] = mapped_column(Date, nullable=False)
    supersedes_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("risk_materiality_rules.id", ondelete="RESTRICT"),
        nullable=True,
    )
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="candidate")
    created_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)

class RiskRun(FinancialBase):
    __tablename__ = "risk_runs"
    __table_args__ = (
        UniqueConstraint("tenant_id", "run_token", name="uq_risk_runs_tenant_token"),
        CheckConstraint(
            "status IN ('created','running','completed','failed')",
            name="ck_risk_runs_status",
        ),
        CheckConstraint(
            "jsonb_typeof(source_metric_run_ids_json) = 'array' AND jsonb_array_length(source_metric_run_ids_json) > 0",
            name="ck_risk_runs_metric_sources_required",
        ),
        CheckConstraint(
            "jsonb_typeof(source_variance_run_ids_json) = 'array' AND jsonb_array_length(source_variance_run_ids_json) > 0",
            name="ck_risk_runs_variance_sources_required",
        ),
        CheckConstraint(
            "jsonb_typeof(source_trend_run_ids_json) = 'array'",
            name="ck_risk_runs_trend_sources_array",
        ),
        CheckConstraint(
            "jsonb_typeof(source_reconciliation_session_ids_json) = 'array'",
            name="ck_risk_runs_reconciliation_sources_array",
        ),
        Index(
            "idx_risk_runs_lookup",
            "tenant_id",
            "organisation_id",
            "reporting_period",
            "created_at",
        ),
        Index("idx_risk_runs_token", "tenant_id", "run_token", unique=True),
    )

    organisation_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    reporting_period: Mapped[date] = mapped_column(Date, nullable=False)
    risk_definition_version_token: Mapped[str] = mapped_column(String(64), nullable=False)
    propagation_version_token: Mapped[str] = mapped_column(String(64), nullable=False)
    weight_version_token: Mapped[str] = mapped_column(String(64), nullable=False)
    materiality_version_token: Mapped[str] = mapped_column(String(64), nullable=False)
    source_metric_run_ids_json: Mapped[list[str]] = mapped_column(
        JSONB, nullable=False, default=list
    )
    source_variance_run_ids_json: Mapped[list[str]] = mapped_column(
        JSONB, nullable=False, default=list
    )
    source_trend_run_ids_json: Mapped[list[str]] = mapped_column(
        JSONB, nullable=False, default=list
    )
    source_reconciliation_session_ids_json: Mapped[list[str]] = mapped_column(
        JSONB, nullable=False, default=list
    )
    run_token: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="created")
    validation_summary_json: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, default=dict
    )
    created_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)


class RiskResult(FinancialBase):
    __tablename__ = "risk_results"
    __table_args__ = (
        UniqueConstraint("run_id", "line_no", name="uq_risk_results_line_no"),
        CheckConstraint(
            "risk_domain IN ('profitability','liquidity','leverage','working_capital','cost_structure','payroll','confidence','reconciliation_dependency','board_critical')",
            name="ck_risk_results_domain",
        ),
        CheckConstraint(
            "severity IN ('info','low','medium','high','critical')",
            name="ck_risk_results_severity",
        ),
        CheckConstraint("risk_score >= 0 AND risk_score <= 1", name="ck_risk_results_score"),
        CheckConstraint(
            "confidence_score >= 0 AND confidence_score <= 1",
            name="ck_risk_results_confidence",
        ),
        CheckConstraint(
            "persistence_state IN ('new','repeated','escalating','deescalating','resolved','reopened')",
            name="ck_risk_results_persistence",
        ),
        Index("idx_risk_results_run", "tenant_id", "run_id", "line_no"),
        Index(
            "idx_risk_results_domain_severity",
            "tenant_id",
            "run_id",
            "risk_domain",
            "severity",
        ),
    )

    run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("risk_runs.id", ondelete="RESTRICT"),
        nullable=False,
    )
    line_no: Mapped[int] = mapped_column(Integer, nullable=False)
    risk_code: Mapped[str] = mapped_column(String(128), nullable=False)
    risk_name: Mapped[str] = mapped_column(String(255), nullable=False)
    risk_domain: Mapped[str] = mapped_column(String(64), nullable=False)
    risk_score: Mapped[Decimal] = mapped_column(Numeric(12, 6), nullable=False)
    severity: Mapped[str] = mapped_column(String(16), nullable=False)
    confidence_score: Mapped[Decimal] = mapped_column(Numeric(12, 6), nullable=False)
    materiality_flag: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    board_attention_flag: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    persistence_state: Mapped[str] = mapped_column(String(32), nullable=False, default="new")
    unresolved_dependency_flag: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )
    source_summary_json: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    created_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)


class RiskContributingSignal(FinancialBase):
    __tablename__ = "risk_contributing_signals"
    __table_args__ = (
        CheckConstraint(
            "signal_type IN ('metric_result','variance_result','trend_result','reconciliation_exception','parent_risk_result')",
            name="ck_risk_contributing_signals_type",
        ),
        CheckConstraint(
            "contribution_weight >= 0 AND contribution_weight <= 10",
            name="ck_risk_contributing_signals_weight",
        ),
        CheckConstraint(
            "contribution_score >= 0 AND contribution_score <= 1",
            name="ck_risk_contributing_signals_score",
        ),
        Index(
            "idx_risk_contributing_signals_run",
            "tenant_id",
            "run_id",
            "risk_result_id",
            "id",
        ),
    )

    run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("risk_runs.id", ondelete="RESTRICT"),
        nullable=False,
    )
    risk_result_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("risk_results.id", ondelete="RESTRICT"),
        nullable=False,
    )
    signal_type: Mapped[str] = mapped_column(String(64), nullable=False)
    signal_ref: Mapped[str] = mapped_column(Text, nullable=False)
    contribution_weight: Mapped[Decimal] = mapped_column(Numeric(12, 6), nullable=False)
    contribution_score: Mapped[Decimal] = mapped_column(Numeric(12, 6), nullable=False)
    signal_payload_json: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    created_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)


class RiskRollforwardEvent(FinancialBase):
    __tablename__ = "risk_rollforward_events"
    __table_args__ = (
        CheckConstraint(
            "event_type IN ('rolled_forward','escalated','deescalated','resolved','reopened','confidence_degraded','confidence_restored')",
            name="ck_risk_rollforward_events_type",
        ),
        Index(
            "idx_risk_rollforward_events_run",
            "tenant_id",
            "run_id",
            "risk_result_id",
            "created_at",
        ),
    )

    run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("risk_runs.id", ondelete="RESTRICT"),
        nullable=False,
    )
    risk_result_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("risk_results.id", ondelete="RESTRICT"),
        nullable=False,
    )
    event_type: Mapped[str] = mapped_column(String(64), nullable=False)
    event_payload_json: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    actor_user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    created_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)


class RiskEvidenceLink(FinancialBase):
    __tablename__ = "risk_evidence_links"
    __table_args__ = (
        CheckConstraint(
            "evidence_type IN ('metric_result','variance_result','trend_result','reconciliation_session','normalized_source','definition_token','run_input')",
            name="ck_risk_evidence_links_type",
        ),
        Index("idx_risk_evidence_links_run", "tenant_id", "run_id", "created_at"),
        Index(
            "idx_risk_evidence_links_result",
            "tenant_id",
            "run_id",
            "risk_result_id",
        ),
    )

    run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("risk_runs.id", ondelete="RESTRICT"),
        nullable=False,
    )
    risk_result_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("risk_results.id", ondelete="RESTRICT"),
        nullable=False,
    )
    evidence_type: Mapped[str] = mapped_column(String(64), nullable=False)
    evidence_ref: Mapped[str] = mapped_column(Text, nullable=False)
    evidence_label: Mapped[str] = mapped_column(String(255), nullable=False)
    created_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
