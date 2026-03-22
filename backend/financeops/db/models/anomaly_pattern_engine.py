from __future__ import annotations

import uuid
from datetime import date, datetime
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


class AnomalyDefinition(FinancialBase):
    __tablename__ = "anomaly_definitions"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "organisation_id",
            "anomaly_code",
            "version_token",
            name="uq_anomaly_definitions_version_token",
        ),
        CheckConstraint(
            "anomaly_domain IN ('profitability','cost_structure','liquidity','working_capital','leverage','payroll','reconciliation_linked')",
            name="ck_anomaly_definitions_domain",
        ),
        CheckConstraint(
            "status IN ('candidate','active','superseded','rejected')",
            name="ck_anomaly_definitions_status",
        ),
        Index(
            "idx_anomaly_definitions_lookup",
            "tenant_id",
            "organisation_id",
            "anomaly_code",
            "effective_from",
            "created_at",
        ),
        Index(
            "uq_anomaly_definitions_one_active",
            "tenant_id",
            "organisation_id",
            "anomaly_code",
            unique=True,
            postgresql_where=text("status = 'active'"),
        ),
    )

    organisation_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    anomaly_code: Mapped[str] = mapped_column(String(128), nullable=False)
    anomaly_name: Mapped[str] = mapped_column(String(255), nullable=False)
    anomaly_domain: Mapped[str] = mapped_column(String(64), nullable=False)
    signal_selector_json: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, default=dict
    )
    definition_json: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    version_token: Mapped[str] = mapped_column(String(64), nullable=False)
    effective_from: Mapped[date] = mapped_column(Date, nullable=False)
    effective_to: Mapped[date | None] = mapped_column(Date, nullable=True)
    supersedes_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("anomaly_definitions.id", ondelete="RESTRICT"),
        nullable=True,
    )
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="candidate")
    created_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)


class AnomalyPatternRule(FinancialBase):
    __tablename__ = "anomaly_pattern_rules"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "organisation_id",
            "rule_code",
            "version_token",
            name="uq_anomaly_pattern_rules_version_token",
        ),
        CheckConstraint(
            "status IN ('candidate','active','superseded','rejected')",
            name="ck_anomaly_pattern_rules_status",
        ),
        Index(
            "idx_anomaly_pattern_rules_lookup",
            "tenant_id",
            "organisation_id",
            "rule_code",
            "effective_from",
            "created_at",
        ),
        Index(
            "uq_anomaly_pattern_rules_one_active",
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
    pattern_signature_json: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, default=dict
    )
    classification_behavior_json: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, default=dict
    )
    version_token: Mapped[str] = mapped_column(String(64), nullable=False)
    effective_from: Mapped[date] = mapped_column(Date, nullable=False)
    supersedes_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("anomaly_pattern_rules.id", ondelete="RESTRICT"),
        nullable=True,
    )
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="candidate")
    created_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)


class AnomalyPersistenceRule(FinancialBase):
    __tablename__ = "anomaly_persistence_rules"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "organisation_id",
            "rule_code",
            "version_token",
            name="uq_anomaly_persistence_rules_version_token",
        ),
        CheckConstraint(
            "rolling_window IN (3,6,12,24)",
            name="ck_anomaly_persistence_rules_rolling_window",
        ),
        CheckConstraint(
            "recurrence_threshold >= 1",
            name="ck_anomaly_persistence_rules_recurrence_threshold",
        ),
        CheckConstraint(
            "status IN ('candidate','active','superseded','rejected')",
            name="ck_anomaly_persistence_rules_status",
        ),
        Index(
            "idx_anomaly_persistence_rules_lookup",
            "tenant_id",
            "organisation_id",
            "rule_code",
            "effective_from",
            "created_at",
        ),
        Index(
            "uq_anomaly_persistence_rules_one_active",
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
    rolling_window: Mapped[int] = mapped_column(Integer, nullable=False)
    recurrence_threshold: Mapped[int] = mapped_column(Integer, nullable=False)
    escalation_logic_json: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, default=dict
    )
    version_token: Mapped[str] = mapped_column(String(64), nullable=False)
    effective_from: Mapped[date] = mapped_column(Date, nullable=False)
    supersedes_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("anomaly_persistence_rules.id", ondelete="RESTRICT"),
        nullable=True,
    )
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="candidate")
    created_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)


class AnomalyCorrelationRule(FinancialBase):
    __tablename__ = "anomaly_correlation_rules"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "organisation_id",
            "rule_code",
            "version_token",
            name="uq_anomaly_correlation_rules_version_token",
        ),
        CheckConstraint(
            "correlation_window IN (3,6,12,24)",
            name="ck_anomaly_correlation_rules_window",
        ),
        CheckConstraint(
            "min_signal_count >= 2",
            name="ck_anomaly_correlation_rules_min_signal_count",
        ),
        CheckConstraint(
            "status IN ('candidate','active','superseded','rejected')",
            name="ck_anomaly_correlation_rules_status",
        ),
        Index(
            "idx_anomaly_correlation_rules_lookup",
            "tenant_id",
            "organisation_id",
            "rule_code",
            "effective_from",
            "created_at",
        ),
        Index(
            "uq_anomaly_correlation_rules_one_active",
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
    correlation_window: Mapped[int] = mapped_column(Integer, nullable=False)
    min_signal_count: Mapped[int] = mapped_column(Integer, nullable=False)
    correlation_logic_json: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, default=dict
    )
    version_token: Mapped[str] = mapped_column(String(64), nullable=False)
    effective_from: Mapped[date] = mapped_column(Date, nullable=False)
    supersedes_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("anomaly_correlation_rules.id", ondelete="RESTRICT"),
        nullable=True,
    )
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="candidate")
    created_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)


class AnomalyStatisticalRule(FinancialBase):
    __tablename__ = "anomaly_statistical_rules"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "organisation_id",
            "rule_code",
            "version_token",
            name="uq_anomaly_statistical_rules_version_token",
        ),
        CheckConstraint(
            "rolling_window IN (3,6,12,24)",
            name="ck_anomaly_statistical_rules_window",
        ),
        CheckConstraint(
            "baseline_type IN ('rolling_mean','rolling_std','rolling_median','rolling_pct_change')",
            name="ck_anomaly_statistical_rules_baseline_type",
        ),
        CheckConstraint(
            "z_threshold > 0",
            name="ck_anomaly_statistical_rules_z_threshold",
        ),
        CheckConstraint(
            "regime_shift_threshold_pct >= 0",
            name="ck_anomaly_statistical_rules_regime_shift_threshold",
        ),
        CheckConstraint(
            "seasonal_period IS NULL OR seasonal_period = 12",
            name="ck_anomaly_statistical_rules_seasonal_period",
        ),
        CheckConstraint(
            "status IN ('candidate','active','superseded','rejected')",
            name="ck_anomaly_statistical_rules_status",
        ),
        Index(
            "idx_anomaly_statistical_rules_lookup",
            "tenant_id",
            "organisation_id",
            "rule_code",
            "effective_from",
            "created_at",
        ),
        Index(
            "uq_anomaly_statistical_rules_one_active",
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
    rolling_window: Mapped[int] = mapped_column(Integer, nullable=False)
    baseline_type: Mapped[str] = mapped_column(String(64), nullable=False)
    z_threshold: Mapped[Decimal] = mapped_column(Numeric(12, 6), nullable=False)
    regime_shift_threshold_pct: Mapped[Decimal] = mapped_column(Numeric(12, 6), nullable=False)
    seasonal_period: Mapped[int | None] = mapped_column(Integer, nullable=True)
    seasonal_adjustment_flag: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    benchmark_group_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    configuration_json: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    version_token: Mapped[str] = mapped_column(String(64), nullable=False)
    effective_from: Mapped[date] = mapped_column(Date, nullable=False)
    supersedes_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("anomaly_statistical_rules.id", ondelete="RESTRICT"),
        nullable=True,
    )
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="candidate")
    created_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)


class AnomalyRun(FinancialBase):
    __tablename__ = "anomaly_runs"
    __table_args__ = (
        UniqueConstraint("tenant_id", "run_token", name="uq_anomaly_runs_tenant_token"),
        CheckConstraint(
            "status IN ('created','running','completed','failed')",
            name="ck_anomaly_runs_status",
        ),
        CheckConstraint(
            "jsonb_typeof(source_metric_run_ids_json) = 'array' AND jsonb_array_length(source_metric_run_ids_json) > 0",
            name="ck_anomaly_runs_metric_sources_required",
        ),
        CheckConstraint(
            "jsonb_typeof(source_variance_run_ids_json) = 'array' AND jsonb_array_length(source_variance_run_ids_json) > 0",
            name="ck_anomaly_runs_variance_sources_required",
        ),
        CheckConstraint(
            "jsonb_typeof(source_trend_run_ids_json) = 'array'",
            name="ck_anomaly_runs_trend_sources_array",
        ),
        CheckConstraint(
            "jsonb_typeof(source_risk_run_ids_json) = 'array'",
            name="ck_anomaly_runs_risk_sources_array",
        ),
        CheckConstraint(
            "jsonb_typeof(source_reconciliation_session_ids_json) = 'array'",
            name="ck_anomaly_runs_reconciliation_sources_array",
        ),
        Index(
            "idx_anomaly_runs_lookup",
            "tenant_id",
            "organisation_id",
            "reporting_period",
            "created_at",
        ),
        Index("idx_anomaly_runs_token", "tenant_id", "run_token", unique=True),
    )

    organisation_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    reporting_period: Mapped[date] = mapped_column(Date, nullable=False)
    anomaly_definition_version_token: Mapped[str] = mapped_column(String(64), nullable=False)
    pattern_rule_version_token: Mapped[str] = mapped_column(String(64), nullable=False)
    persistence_rule_version_token: Mapped[str] = mapped_column(String(64), nullable=False)
    correlation_rule_version_token: Mapped[str] = mapped_column(String(64), nullable=False)
    statistical_rule_version_token: Mapped[str] = mapped_column(String(64), nullable=False)
    source_metric_run_ids_json: Mapped[list[str]] = mapped_column(
        JSONB, nullable=False, default=list
    )
    source_variance_run_ids_json: Mapped[list[str]] = mapped_column(
        JSONB, nullable=False, default=list
    )
    source_trend_run_ids_json: Mapped[list[str]] = mapped_column(
        JSONB, nullable=False, default=list
    )
    source_risk_run_ids_json: Mapped[list[str]] = mapped_column(
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


class AnomalyResult(FinancialBase):
    __tablename__ = "anomaly_results"
    __table_args__ = (
        UniqueConstraint("run_id", "line_no", name="uq_anomaly_results_line_no"),
        CheckConstraint(
            "anomaly_domain IN ('profitability','cost_structure','liquidity','working_capital','leverage','payroll','reconciliation_linked')",
            name="ck_anomaly_results_domain",
        ),
        CheckConstraint(
            "severity IN ('info','low','medium','high','critical')",
            name="ck_anomaly_results_severity",
        ),
        CheckConstraint("anomaly_score >= 0 AND anomaly_score <= 1", name="ck_anomaly_results_score"),
        CheckConstraint(
            "confidence_score >= 0 AND confidence_score <= 1",
            name="ck_anomaly_results_confidence",
        ),
        CheckConstraint(
            "persistence_classification IN ('first_detected','recurring','sustained','escalating','resolved','reopened')",
            name="ck_anomaly_results_persistence",
        ),
        CheckConstraint(
            "alert_status IN ('OPEN','SNOOZED','RESOLVED','ESCALATED')",
            name="ck_anomaly_results_alert_status",
        ),
        Index("idx_anomaly_results_run", "tenant_id", "run_id", "line_no"),
        Index(
            "idx_anomaly_results_domain_severity",
            "tenant_id",
            "run_id",
            "anomaly_domain",
            "severity",
        ),
    )

    run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("anomaly_runs.id", ondelete="RESTRICT"),
        nullable=False,
    )
    line_no: Mapped[int] = mapped_column(Integer, nullable=False)
    anomaly_code: Mapped[str] = mapped_column(String(128), nullable=False)
    anomaly_name: Mapped[str] = mapped_column(String(255), nullable=False)
    anomaly_domain: Mapped[str] = mapped_column(String(64), nullable=False)
    anomaly_score: Mapped[Decimal] = mapped_column(Numeric(12, 6), nullable=False)
    z_score: Mapped[Decimal | None] = mapped_column(Numeric(12, 6), nullable=True)
    severity: Mapped[str] = mapped_column(String(16), nullable=False)
    alert_status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        server_default=text("'OPEN'"),
        default="OPEN",
    )
    snoozed_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    escalated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    status_updated_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        nullable=True,
    )
    persistence_classification: Mapped[str] = mapped_column(String(32), nullable=False)
    correlation_flag: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    materiality_elevated: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    risk_elevated: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    board_flag: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    confidence_score: Mapped[Decimal] = mapped_column(Numeric(12, 6), nullable=False)
    seasonal_adjustment_flag: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    seasonal_normalized_value: Mapped[Decimal | None] = mapped_column(Numeric(20, 6), nullable=True)
    benchmark_group_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    benchmark_baseline_value: Mapped[Decimal | None] = mapped_column(Numeric(20, 6), nullable=True)
    benchmark_deviation_score: Mapped[Decimal | None] = mapped_column(Numeric(20, 6), nullable=True)
    source_summary_json: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    created_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)


class AnomalyContributingSignal(FinancialBase):
    __tablename__ = "anomaly_contributing_signals"
    __table_args__ = (
        CheckConstraint(
            "signal_type IN ('metric_ref','variance_ref','trend_ref','risk_ref','reconciliation_ref','statistical_baseline_ref','parent_anomaly_ref')",
            name="ck_anomaly_contributing_signals_type",
        ),
        CheckConstraint(
            "contribution_weight >= 0 AND contribution_weight <= 10",
            name="ck_anomaly_contributing_signals_weight",
        ),
        CheckConstraint(
            "contribution_score >= 0 AND contribution_score <= 1",
            name="ck_anomaly_contributing_signals_score",
        ),
        Index(
            "idx_anomaly_contributing_signals_run",
            "tenant_id",
            "run_id",
            "anomaly_result_id",
            "id",
        ),
    )

    run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("anomaly_runs.id", ondelete="RESTRICT"),
        nullable=False,
    )
    anomaly_result_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("anomaly_results.id", ondelete="RESTRICT"),
        nullable=False,
    )
    signal_type: Mapped[str] = mapped_column(String(64), nullable=False)
    signal_ref: Mapped[str] = mapped_column(Text, nullable=False)
    contribution_weight: Mapped[Decimal] = mapped_column(Numeric(12, 6), nullable=False)
    contribution_score: Mapped[Decimal] = mapped_column(Numeric(12, 6), nullable=False)
    signal_payload_json: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    created_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)


class AnomalyRollforwardEvent(FinancialBase):
    __tablename__ = "anomaly_rollforward_events"
    __table_args__ = (
        CheckConstraint(
            "event_type IN ('rolled_forward','escalated','deescalated','resolved','reopened','recurrence_detected','correlation_strengthened','correlation_weakened')",
            name="ck_anomaly_rollforward_events_type",
        ),
        Index(
            "idx_anomaly_rollforward_events_run",
            "tenant_id",
            "run_id",
            "anomaly_result_id",
            "created_at",
        ),
    )

    run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("anomaly_runs.id", ondelete="RESTRICT"),
        nullable=False,
    )
    anomaly_result_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("anomaly_results.id", ondelete="RESTRICT"),
        nullable=False,
    )
    event_type: Mapped[str] = mapped_column(String(64), nullable=False)
    event_payload_json: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    actor_user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    created_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)


class AnomalyEvidenceLink(FinancialBase):
    __tablename__ = "anomaly_evidence_links"
    __table_args__ = (
        CheckConstraint(
            "evidence_type IN ('metric_result','variance_result','trend_result','risk_result','reconciliation_session','normalized_source','definition_token','statistical_rule_token','persistence_rule_token','correlation_rule_token','run_input')",
            name="ck_anomaly_evidence_links_type",
        ),
        Index("idx_anomaly_evidence_links_run", "tenant_id", "run_id", "created_at"),
        Index(
            "idx_anomaly_evidence_links_result",
            "tenant_id",
            "run_id",
            "anomaly_result_id",
        ),
    )

    run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("anomaly_runs.id", ondelete="RESTRICT"),
        nullable=False,
    )
    anomaly_result_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("anomaly_results.id", ondelete="RESTRICT"),
        nullable=False,
    )
    evidence_type: Mapped[str] = mapped_column(String(64), nullable=False)
    evidence_ref: Mapped[str] = mapped_column(Text, nullable=False)
    evidence_label: Mapped[str] = mapped_column(String(255), nullable=False)
    created_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
