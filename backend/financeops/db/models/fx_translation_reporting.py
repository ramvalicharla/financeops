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


class ReportingCurrencyDefinition(FinancialBase):
    __tablename__ = "reporting_currency_definitions"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "organisation_id",
            "reporting_currency_code",
            "reporting_scope_type",
            "reporting_scope_ref",
            "version_token",
            name="uq_reporting_currency_definitions_version_token",
        ),
        CheckConstraint(
            "status IN ('candidate','active','superseded','rejected')",
            name="ck_reporting_currency_definitions_status",
        ),
        Index(
            "idx_reporting_currency_definitions_lookup",
            "tenant_id",
            "organisation_id",
            "reporting_scope_type",
            "reporting_scope_ref",
            "effective_from",
            "created_at",
        ),
        Index(
            "uq_reporting_currency_definitions_one_active_scope",
            "tenant_id",
            "organisation_id",
            "reporting_scope_type",
            "reporting_scope_ref",
            unique=True,
            postgresql_where=text("status = 'active'"),
        ),
    )

    organisation_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    reporting_currency_code: Mapped[str] = mapped_column(String(3), nullable=False)
    reporting_currency_name: Mapped[str] = mapped_column(String(128), nullable=False)
    reporting_scope_type: Mapped[str] = mapped_column(String(64), nullable=False)
    reporting_scope_ref: Mapped[str] = mapped_column(String(128), nullable=False)
    version_token: Mapped[str] = mapped_column(String(64), nullable=False)
    effective_from: Mapped[date] = mapped_column(Date, nullable=False)
    effective_to: Mapped[date | None] = mapped_column(Date, nullable=True)
    supersedes_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("reporting_currency_definitions.id", ondelete="RESTRICT"),
        nullable=True,
    )
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="candidate")
    created_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)


class FxTranslationRuleDefinition(FinancialBase):
    __tablename__ = "fx_translation_rule_definitions"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "organisation_id",
            "rule_code",
            "version_token",
            name="uq_fx_translation_rule_definitions_version_token",
        ),
        CheckConstraint(
            "status IN ('candidate','active','superseded','rejected')",
            name="ck_fx_translation_rule_definitions_status",
        ),
        Index(
            "idx_fx_translation_rule_definitions_lookup",
            "tenant_id",
            "organisation_id",
            "rule_code",
            "effective_from",
            "created_at",
        ),
        Index(
            "uq_fx_translation_rule_definitions_one_active",
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
    translation_scope_type: Mapped[str] = mapped_column(String(64), nullable=False)
    translation_scope_ref: Mapped[str] = mapped_column(String(128), nullable=False)
    source_currency_selector_json: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, default=dict
    )
    target_reporting_currency_code: Mapped[str] = mapped_column(String(3), nullable=False)
    rule_logic_json: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    rate_policy_ref: Mapped[str] = mapped_column(String(128), nullable=False)
    version_token: Mapped[str] = mapped_column(String(64), nullable=False)
    effective_from: Mapped[date] = mapped_column(Date, nullable=False)
    effective_to: Mapped[date | None] = mapped_column(Date, nullable=True)
    supersedes_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("fx_translation_rule_definitions.id", ondelete="RESTRICT"),
        nullable=True,
    )
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="candidate")
    created_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)


class FxRateSelectionPolicy(FinancialBase):
    __tablename__ = "fx_rate_selection_policies"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "organisation_id",
            "policy_code",
            "version_token",
            name="uq_fx_rate_selection_policies_version_token",
        ),
        CheckConstraint(
            "rate_type IN ('closing','average','historical')",
            name="ck_fx_rate_selection_policies_rate_type",
        ),
        CheckConstraint(
            "status IN ('candidate','active','superseded','rejected')",
            name="ck_fx_rate_selection_policies_status",
        ),
        Index(
            "idx_fx_rate_selection_policies_lookup",
            "tenant_id",
            "organisation_id",
            "policy_code",
            "effective_from",
            "created_at",
        ),
        Index(
            "uq_fx_rate_selection_policies_one_active",
            "tenant_id",
            "organisation_id",
            "policy_code",
            unique=True,
            postgresql_where=text("status = 'active'"),
        ),
    )

    organisation_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    policy_code: Mapped[str] = mapped_column(String(128), nullable=False)
    policy_name: Mapped[str] = mapped_column(String(255), nullable=False)
    rate_type: Mapped[str] = mapped_column(String(32), nullable=False)
    date_selector_logic_json: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    fallback_behavior_json: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    locked_rate_requirement_flag: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    source_rate_provider_ref: Mapped[str] = mapped_column(String(128), nullable=False, default="fx_rate_tables_v1")
    version_token: Mapped[str] = mapped_column(String(64), nullable=False)
    effective_from: Mapped[date] = mapped_column(Date, nullable=False)
    effective_to: Mapped[date | None] = mapped_column(Date, nullable=True)
    supersedes_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("fx_rate_selection_policies.id", ondelete="RESTRICT"),
        nullable=True,
    )
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="candidate")
    created_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)


class FxTranslationRun(FinancialBase):
    __tablename__ = "fx_translation_runs"
    __table_args__ = (
        UniqueConstraint("tenant_id", "run_token", name="uq_fx_translation_runs_tenant_token"),
        CheckConstraint(
            "run_status IN ('created','running','completed','failed')",
            name="ck_fx_translation_runs_status",
        ),
        CheckConstraint(
            "jsonb_typeof(source_consolidation_run_refs_json) = 'array' AND jsonb_array_length(source_consolidation_run_refs_json) > 0",
            name="ck_fx_translation_runs_sources_required",
        ),
        Index(
            "idx_fx_translation_runs_lookup",
            "tenant_id",
            "organisation_id",
            "reporting_period",
            "created_at",
        ),
        Index("idx_fx_translation_runs_token", "tenant_id", "run_token", unique=True),
    )

    organisation_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    reporting_period: Mapped[date] = mapped_column(Date, nullable=False)
    reporting_currency_code: Mapped[str] = mapped_column(String(3), nullable=False)
    reporting_currency_version_token: Mapped[str] = mapped_column(String(64), nullable=False)
    translation_rule_version_token: Mapped[str] = mapped_column(String(64), nullable=False)
    rate_policy_version_token: Mapped[str] = mapped_column(String(64), nullable=False)
    rate_source_version_token: Mapped[str] = mapped_column(String(64), nullable=False)
    source_consolidation_run_refs_json: Mapped[list[dict[str, Any]]] = mapped_column(
        JSONB, nullable=False, default=list
    )
    run_token: Mapped[str] = mapped_column(String(64), nullable=False)
    run_status: Mapped[str] = mapped_column(String(32), nullable=False, default="created")
    validation_summary_json: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, default=dict
    )
    created_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)


class FxTranslatedMetricResult(FinancialBase):
    __tablename__ = "fx_translated_metric_results"
    __table_args__ = (
        UniqueConstraint("run_id", "line_no", name="uq_fx_translated_metric_results_line_no"),
        Index("idx_fx_translated_metric_results_run", "tenant_id", "run_id", "line_no"),
        Index(
            "idx_fx_translated_metric_results_source",
            "tenant_id",
            "run_id",
            "source_metric_result_id",
        ),
    )

    run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("fx_translation_runs.id", ondelete="RESTRICT"),
        nullable=False,
    )
    line_no: Mapped[int] = mapped_column(Integer, nullable=False)
    source_metric_result_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("multi_entity_consolidation_metric_results.id", ondelete="RESTRICT"),
        nullable=False,
    )
    metric_code: Mapped[str] = mapped_column(String(128), nullable=False)
    source_currency_code: Mapped[str] = mapped_column(String(3), nullable=False)
    reporting_currency_code: Mapped[str] = mapped_column(String(3), nullable=False)
    applied_rate_type: Mapped[str] = mapped_column(String(32), nullable=False)
    applied_rate_ref: Mapped[str] = mapped_column(String(255), nullable=False)
    applied_rate_value: Mapped[Decimal] = mapped_column(Numeric(20, 8), nullable=False)
    source_value: Mapped[Decimal] = mapped_column(Numeric(20, 6), nullable=False)
    translated_value: Mapped[Decimal] = mapped_column(Numeric(20, 6), nullable=False)
    lineage_json: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    created_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)


class FxTranslatedVarianceResult(FinancialBase):
    __tablename__ = "fx_translated_variance_results"
    __table_args__ = (
        UniqueConstraint("run_id", "line_no", name="uq_fx_translated_variance_results_line_no"),
        CheckConstraint(
            "comparison_type IN ('mom','yoy','actual_vs_budget','actual_vs_forecast')",
            name="ck_fx_translated_variance_results_type",
        ),
        Index("idx_fx_translated_variance_results_run", "tenant_id", "run_id", "line_no"),
        Index(
            "idx_fx_translated_variance_results_source",
            "tenant_id",
            "run_id",
            "source_variance_result_id",
        ),
    )

    run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("fx_translation_runs.id", ondelete="RESTRICT"),
        nullable=False,
    )
    line_no: Mapped[int] = mapped_column(Integer, nullable=False)
    source_variance_result_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("multi_entity_consolidation_variance_results.id", ondelete="RESTRICT"),
        nullable=False,
    )
    metric_code: Mapped[str] = mapped_column(String(128), nullable=False)
    comparison_type: Mapped[str] = mapped_column(String(32), nullable=False)
    source_currency_code: Mapped[str] = mapped_column(String(3), nullable=False)
    reporting_currency_code: Mapped[str] = mapped_column(String(3), nullable=False)
    applied_rate_type: Mapped[str] = mapped_column(String(32), nullable=False)
    applied_rate_ref: Mapped[str] = mapped_column(String(255), nullable=False)
    applied_rate_value: Mapped[Decimal] = mapped_column(Numeric(20, 8), nullable=False)
    source_base_value: Mapped[Decimal] = mapped_column(Numeric(20, 6), nullable=False)
    source_current_value: Mapped[Decimal] = mapped_column(Numeric(20, 6), nullable=False)
    source_variance_value: Mapped[Decimal] = mapped_column(Numeric(20, 6), nullable=False)
    translated_base_value: Mapped[Decimal] = mapped_column(Numeric(20, 6), nullable=False)
    translated_current_value: Mapped[Decimal] = mapped_column(Numeric(20, 6), nullable=False)
    translated_variance_value: Mapped[Decimal] = mapped_column(Numeric(20, 6), nullable=False)
    variance_pct: Mapped[Decimal | None] = mapped_column(Numeric(20, 6), nullable=True)
    lineage_json: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    created_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)


class FxTranslationEvidenceLink(FinancialBase):
    __tablename__ = "fx_translation_evidence_links"
    __table_args__ = (
        CheckConstraint(
            "evidence_type IN ('source_result','applied_rate','rate_type','rule_version','policy_version','rate_source','consolidation_run_ref')",
            name="ck_fx_translation_evidence_links_type",
        ),
        Index("idx_fx_translation_evidence_links_run", "tenant_id", "run_id", "created_at"),
    )

    run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("fx_translation_runs.id", ondelete="RESTRICT"),
        nullable=False,
    )
    translated_metric_result_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("fx_translated_metric_results.id", ondelete="RESTRICT"),
        nullable=True,
    )
    translated_variance_result_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("fx_translated_variance_results.id", ondelete="RESTRICT"),
        nullable=True,
    )
    evidence_type: Mapped[str] = mapped_column(String(64), nullable=False)
    evidence_ref: Mapped[str] = mapped_column(Text, nullable=False)
    evidence_label: Mapped[str] = mapped_column(String(255), nullable=False)
    evidence_payload_json: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    created_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)

