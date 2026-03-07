from __future__ import annotations

import uuid
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


class MetricDefinition(FinancialBase):
    __tablename__ = "metric_definitions"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "organisation_id",
            "definition_code",
            "version_token",
            name="uq_metric_definitions_version_token",
        ),
        CheckConstraint(
            "formula_type IN ('sum','ratio','difference','direct','custom_expression')",
            name="ck_metric_definitions_formula_type",
        ),
        CheckConstraint(
            "directionality IN ('higher_is_better','lower_is_better','neutral','contextual')",
            name="ck_metric_definitions_directionality",
        ),
        CheckConstraint(
            "status IN ('candidate','active','superseded','rejected')",
            name="ck_metric_definitions_status",
        ),
        Index(
            "idx_metric_definitions_lookup",
            "tenant_id",
            "organisation_id",
            "definition_code",
            "effective_from",
            "created_at",
        ),
        Index(
            "uq_metric_definitions_one_active",
            "tenant_id",
            "organisation_id",
            "definition_code",
            unique=True,
            postgresql_where=text("status = 'active'"),
        ),
    )

    organisation_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    definition_code: Mapped[str] = mapped_column(String(128), nullable=False)
    definition_name: Mapped[str] = mapped_column(String(255), nullable=False)
    metric_code: Mapped[str] = mapped_column(String(128), nullable=False)
    formula_type: Mapped[str] = mapped_column(String(64), nullable=False)
    formula_json: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    unit_type: Mapped[str] = mapped_column(String(32), nullable=False, default="amount")
    directionality: Mapped[str] = mapped_column(
        String(32), nullable=False, default="neutral"
    )
    version_token: Mapped[str] = mapped_column(String(64), nullable=False)
    effective_from: Mapped[Any] = mapped_column(Date, nullable=False)
    supersedes_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("metric_definitions.id", ondelete="RESTRICT"),
        nullable=True,
    )
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="candidate")
    created_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)


class MetricDefinitionComponent(FinancialBase):
    __tablename__ = "metric_definition_components"
    __table_args__ = (
        UniqueConstraint(
            "metric_definition_id",
            "component_code",
            name="uq_metric_definition_components_code",
        ),
        UniqueConstraint(
            "metric_definition_id",
            "ordinal_position",
            name="uq_metric_definition_components_ordinal",
        ),
        CheckConstraint(
            "source_type IN ('mis_metric','payroll_metric','gl_account_prefix','metric_ref','constant')",
            name="ck_metric_definition_components_source_type",
        ),
        CheckConstraint(
            "operator IN ('add','subtract','multiply','divide','none')",
            name="ck_metric_definition_components_operator",
        ),
        Index(
            "idx_metric_definition_components_metric",
            "tenant_id",
            "metric_definition_id",
            "ordinal_position",
        ),
    )

    metric_definition_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("metric_definitions.id", ondelete="CASCADE"),
        nullable=False,
    )
    component_code: Mapped[str] = mapped_column(String(128), nullable=False)
    source_type: Mapped[str] = mapped_column(String(64), nullable=False)
    source_key: Mapped[str] = mapped_column(String(255), nullable=False)
    operator: Mapped[str] = mapped_column(String(16), nullable=False, default="add")
    weight: Mapped[Decimal] = mapped_column(
        Numeric(20, 6), nullable=False, default=Decimal("1")
    )
    ordinal_position: Mapped[int] = mapped_column(Integer, nullable=False)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    created_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)


class VarianceDefinition(FinancialBase):
    __tablename__ = "variance_definitions"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "organisation_id",
            "definition_code",
            "version_token",
            name="uq_variance_definitions_version_token",
        ),
        CheckConstraint(
            "comparison_type IN ("
            "'mom_abs_pct','yoy_abs_pct','actual_vs_budget_abs_pct',"
            "'actual_vs_forecast_abs_pct','basis_points_change','days_change'"
            ")",
            name="ck_variance_definitions_comparison_type",
        ),
        CheckConstraint(
            "status IN ('candidate','active','superseded','rejected')",
            name="ck_variance_definitions_status",
        ),
        Index(
            "idx_variance_definitions_lookup",
            "tenant_id",
            "organisation_id",
            "definition_code",
            "effective_from",
            "created_at",
        ),
        Index(
            "uq_variance_definitions_one_active",
            "tenant_id",
            "organisation_id",
            "definition_code",
            unique=True,
            postgresql_where=text("status = 'active'"),
        ),
    )

    organisation_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    definition_code: Mapped[str] = mapped_column(String(128), nullable=False)
    definition_name: Mapped[str] = mapped_column(String(255), nullable=False)
    metric_code: Mapped[str] = mapped_column(String(128), nullable=False)
    comparison_type: Mapped[str] = mapped_column(String(64), nullable=False)
    configuration_json: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, default=dict
    )
    version_token: Mapped[str] = mapped_column(String(64), nullable=False)
    effective_from: Mapped[Any] = mapped_column(Date, nullable=False)
    supersedes_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("variance_definitions.id", ondelete="RESTRICT"),
        nullable=True,
    )
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="candidate")
    created_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)


class TrendDefinition(FinancialBase):
    __tablename__ = "trend_definitions"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "organisation_id",
            "definition_code",
            "version_token",
            name="uq_trend_definitions_version_token",
        ),
        CheckConstraint(
            "trend_type IN ('rolling_average','trailing_total','directional')",
            name="ck_trend_definitions_trend_type",
        ),
        CheckConstraint(
            "window_size IN (3,6,12)",
            name="ck_trend_definitions_window_size",
        ),
        CheckConstraint(
            "status IN ('candidate','active','superseded','rejected')",
            name="ck_trend_definitions_status",
        ),
        Index(
            "idx_trend_definitions_lookup",
            "tenant_id",
            "organisation_id",
            "definition_code",
            "effective_from",
            "created_at",
        ),
        Index(
            "uq_trend_definitions_one_active",
            "tenant_id",
            "organisation_id",
            "definition_code",
            unique=True,
            postgresql_where=text("status = 'active'"),
        ),
    )

    organisation_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    definition_code: Mapped[str] = mapped_column(String(128), nullable=False)
    definition_name: Mapped[str] = mapped_column(String(255), nullable=False)
    metric_code: Mapped[str] = mapped_column(String(128), nullable=False)
    trend_type: Mapped[str] = mapped_column(String(64), nullable=False)
    window_size: Mapped[int] = mapped_column(Integer, nullable=False)
    configuration_json: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, default=dict
    )
    version_token: Mapped[str] = mapped_column(String(64), nullable=False)
    effective_from: Mapped[Any] = mapped_column(Date, nullable=False)
    supersedes_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("trend_definitions.id", ondelete="RESTRICT"),
        nullable=True,
    )
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="candidate")
    created_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)


class MaterialityRule(FinancialBase):
    __tablename__ = "materiality_rules"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "organisation_id",
            "definition_code",
            "version_token",
            name="uq_materiality_rules_version_token",
        ),
        CheckConstraint(
            "status IN ('candidate','active','superseded','rejected')",
            name="ck_materiality_rules_status",
        ),
        Index(
            "idx_materiality_rules_lookup",
            "tenant_id",
            "organisation_id",
            "definition_code",
            "effective_from",
            "created_at",
        ),
        Index(
            "uq_materiality_rules_one_active",
            "tenant_id",
            "organisation_id",
            "definition_code",
            unique=True,
            postgresql_where=text("status = 'active'"),
        ),
    )

    organisation_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    definition_code: Mapped[str] = mapped_column(String(128), nullable=False)
    definition_name: Mapped[str] = mapped_column(String(255), nullable=False)
    rule_json: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    version_token: Mapped[str] = mapped_column(String(64), nullable=False)
    effective_from: Mapped[Any] = mapped_column(Date, nullable=False)
    supersedes_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("materiality_rules.id", ondelete="RESTRICT"),
        nullable=True,
    )
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="candidate")
    created_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)


class MetricRun(FinancialBase):
    __tablename__ = "metric_runs"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "run_token",
            name="uq_metric_runs_tenant_token",
        ),
        CheckConstraint(
            "status IN ('created','running','completed','failed')",
            name="ck_metric_runs_status",
        ),
        CheckConstraint(
            "("
            "mis_snapshot_id IS NOT NULL OR "
            "payroll_run_id IS NOT NULL OR "
            "gl_run_id IS NOT NULL OR "
            "reconciliation_session_id IS NOT NULL OR "
            "payroll_gl_reconciliation_run_id IS NOT NULL"
            ")",
            name="ck_metric_runs_requires_input_reference",
        ),
        Index(
            "idx_metric_runs_lookup",
            "tenant_id",
            "organisation_id",
            "reporting_period",
            "created_at",
        ),
        Index("idx_metric_runs_token", "tenant_id", "run_token", unique=True),
    )

    organisation_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    reporting_period: Mapped[Any] = mapped_column(Date, nullable=False)
    scope_json: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    mis_snapshot_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("mis_data_snapshots.id", ondelete="RESTRICT"),
        nullable=True,
    )
    payroll_run_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("normalization_runs.id", ondelete="RESTRICT"),
        nullable=True,
    )
    gl_run_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("normalization_runs.id", ondelete="RESTRICT"),
        nullable=True,
    )
    reconciliation_session_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("reconciliation_sessions.id", ondelete="RESTRICT"),
        nullable=True,
    )
    payroll_gl_reconciliation_run_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("payroll_gl_reconciliation_runs.id", ondelete="RESTRICT"),
        nullable=True,
    )
    metric_definition_version_token: Mapped[str] = mapped_column(String(64), nullable=False)
    variance_definition_version_token: Mapped[str] = mapped_column(String(64), nullable=False)
    trend_definition_version_token: Mapped[str] = mapped_column(String(64), nullable=False)
    materiality_rule_version_token: Mapped[str] = mapped_column(String(64), nullable=False)
    input_signature_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    run_token: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="created")
    created_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)


class MetricResult(FinancialBase):
    __tablename__ = "metric_results"
    __table_args__ = (
        UniqueConstraint("run_id", "line_no", name="uq_metric_results_line_no"),
        CheckConstraint(
            "unit_type IN ('amount','percentage','ratio','days','count','bps')",
            name="ck_metric_results_unit_type",
        ),
        CheckConstraint(
            "favorable_status IN ('favorable','unfavorable','neutral')",
            name="ck_metric_results_favorable_status",
        ),
        Index("idx_metric_results_run", "tenant_id", "run_id", "line_no"),
        Index("idx_metric_results_metric", "tenant_id", "run_id", "metric_code"),
    )

    run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("metric_runs.id", ondelete="CASCADE"),
        nullable=False,
    )
    line_no: Mapped[int] = mapped_column(Integer, nullable=False)
    metric_code: Mapped[str] = mapped_column(String(128), nullable=False)
    unit_type: Mapped[str] = mapped_column(String(32), nullable=False)
    dimension_json: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    metric_value: Mapped[Decimal] = mapped_column(Numeric(20, 6), nullable=False)
    favorable_status: Mapped[str] = mapped_column(String(16), nullable=False, default="neutral")
    materiality_flag: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    source_summary_json: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, default=dict
    )
    created_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)


class VarianceResult(FinancialBase):
    __tablename__ = "variance_results"
    __table_args__ = (
        UniqueConstraint("run_id", "line_no", name="uq_variance_results_line_no"),
        CheckConstraint(
            "comparison_type IN ("
            "'mom_abs_pct','yoy_abs_pct','actual_vs_budget_abs_pct',"
            "'actual_vs_forecast_abs_pct','basis_points_change','days_change'"
            ")",
            name="ck_variance_results_comparison_type",
        ),
        CheckConstraint(
            "favorable_status IN ('favorable','unfavorable','neutral')",
            name="ck_variance_results_favorable_status",
        ),
        Index("idx_variance_results_run", "tenant_id", "run_id", "line_no"),
        Index(
            "idx_variance_results_metric_comparison",
            "tenant_id",
            "run_id",
            "metric_code",
            "comparison_type",
        ),
    )

    run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("metric_runs.id", ondelete="CASCADE"),
        nullable=False,
    )
    line_no: Mapped[int] = mapped_column(Integer, nullable=False)
    metric_code: Mapped[str] = mapped_column(String(128), nullable=False)
    comparison_type: Mapped[str] = mapped_column(String(64), nullable=False)
    base_period: Mapped[Any | None] = mapped_column(Date, nullable=True)
    current_value: Mapped[Decimal] = mapped_column(Numeric(20, 6), nullable=False)
    baseline_value: Mapped[Decimal] = mapped_column(Numeric(20, 6), nullable=False)
    variance_abs: Mapped[Decimal] = mapped_column(Numeric(20, 6), nullable=False)
    variance_pct: Mapped[Decimal] = mapped_column(Numeric(20, 6), nullable=False)
    variance_bps: Mapped[Decimal] = mapped_column(Numeric(20, 6), nullable=False)
    days_change: Mapped[Decimal] = mapped_column(Numeric(20, 6), nullable=False)
    favorable_status: Mapped[str] = mapped_column(String(16), nullable=False, default="neutral")
    materiality_flag: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    explanation_hint: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)


class TrendResult(FinancialBase):
    __tablename__ = "trend_results"
    __table_args__ = (
        UniqueConstraint("run_id", "line_no", name="uq_trend_results_line_no"),
        CheckConstraint(
            "trend_type IN ('rolling_average','trailing_total','directional')",
            name="ck_trend_results_trend_type",
        ),
        CheckConstraint("window_size IN (3,6,12)", name="ck_trend_results_window_size"),
        CheckConstraint(
            "trend_direction IN ('up','down','flat','na')",
            name="ck_trend_results_direction",
        ),
        Index("idx_trend_results_run", "tenant_id", "run_id", "line_no"),
        Index("idx_trend_results_metric", "tenant_id", "run_id", "metric_code"),
    )

    run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("metric_runs.id", ondelete="CASCADE"),
        nullable=False,
    )
    line_no: Mapped[int] = mapped_column(Integer, nullable=False)
    metric_code: Mapped[str] = mapped_column(String(128), nullable=False)
    trend_type: Mapped[str] = mapped_column(String(64), nullable=False)
    window_size: Mapped[int] = mapped_column(Integer, nullable=False)
    trend_value: Mapped[Decimal] = mapped_column(Numeric(20, 6), nullable=False)
    trend_direction: Mapped[str] = mapped_column(String(16), nullable=False)
    source_summary_json: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, default=dict
    )
    created_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)


class MetricEvidenceLink(FinancialBase):
    __tablename__ = "metric_evidence_links"
    __table_args__ = (
        CheckConstraint(
            "result_type IN ('metric','variance','trend')",
            name="ck_metric_evidence_links_result_type",
        ),
        CheckConstraint(
            "evidence_type IN ("
            "'payroll_normalized_line','gl_normalized_line','mis_normalized_line',"
            "'reconciliation_line','definition','run_input'"
            ")",
            name="ck_metric_evidence_links_evidence_type",
        ),
        Index("idx_metric_evidence_links_run", "tenant_id", "run_id", "created_at"),
        Index(
            "idx_metric_evidence_links_result",
            "tenant_id",
            "run_id",
            "result_type",
            "result_id",
        ),
    )

    run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("metric_runs.id", ondelete="CASCADE"),
        nullable=False,
    )
    result_type: Mapped[str] = mapped_column(String(16), nullable=False)
    result_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    evidence_type: Mapped[str] = mapped_column(String(64), nullable=False)
    evidence_ref: Mapped[str] = mapped_column(Text, nullable=False)
    evidence_label: Mapped[str] = mapped_column(String(255), nullable=False)
    created_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
