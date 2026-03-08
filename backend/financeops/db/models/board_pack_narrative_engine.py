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


class BoardPackDefinition(FinancialBase):
    __tablename__ = "board_pack_definitions"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "organisation_id",
            "board_pack_code",
            "version_token",
            name="uq_board_pack_definitions_version_token",
        ),
        CheckConstraint(
            "status IN ('candidate','active','superseded','rejected')",
            name="ck_board_pack_definitions_status",
        ),
        Index(
            "idx_board_pack_definitions_lookup",
            "tenant_id",
            "organisation_id",
            "board_pack_code",
            "effective_from",
            "created_at",
        ),
        Index(
            "uq_board_pack_definitions_one_active",
            "tenant_id",
            "organisation_id",
            "board_pack_code",
            unique=True,
            postgresql_where=text("status = 'active'"),
        ),
    )

    organisation_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    board_pack_code: Mapped[str] = mapped_column(String(128), nullable=False)
    board_pack_name: Mapped[str] = mapped_column(String(255), nullable=False)
    audience_scope: Mapped[str] = mapped_column(String(64), nullable=False, default="board")
    section_order_json: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    inclusion_config_json: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, default=dict
    )
    version_token: Mapped[str] = mapped_column(String(64), nullable=False)
    effective_from: Mapped[date] = mapped_column(Date, nullable=False)
    effective_to: Mapped[date | None] = mapped_column(Date, nullable=True)
    supersedes_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("board_pack_definitions.id", ondelete="RESTRICT"),
        nullable=True,
    )
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="candidate")
    created_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)


class BoardPackSectionDefinition(FinancialBase):
    __tablename__ = "board_pack_section_definitions"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "organisation_id",
            "section_code",
            "version_token",
            name="uq_board_pack_section_definitions_version_token",
        ),
        CheckConstraint(
            "section_type IN ('executive_summary','financial_performance','profitability_summary','liquidity_summary','payroll_summary','working_capital_summary','key_risks','anomaly_watchlist','reconciliations_and_controls','outlook_placeholder','board_attention_items')",
            name="ck_board_pack_section_definitions_type",
        ),
        CheckConstraint(
            "status IN ('candidate','active','superseded','rejected')",
            name="ck_board_pack_section_definitions_status",
        ),
        Index(
            "idx_board_pack_section_definitions_lookup",
            "tenant_id",
            "organisation_id",
            "section_code",
            "effective_from",
            "created_at",
        ),
        Index(
            "uq_board_pack_section_definitions_one_active",
            "tenant_id",
            "organisation_id",
            "section_code",
            unique=True,
            postgresql_where=text("status = 'active'"),
        ),
    )

    organisation_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    section_code: Mapped[str] = mapped_column(String(128), nullable=False)
    section_name: Mapped[str] = mapped_column(String(255), nullable=False)
    section_type: Mapped[str] = mapped_column(String(64), nullable=False)
    render_logic_json: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    section_order_default: Mapped[int] = mapped_column(Integer, nullable=False)
    narrative_template_ref: Mapped[str | None] = mapped_column(String(128), nullable=True)
    risk_inclusion_rule_json: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, default=dict
    )
    anomaly_inclusion_rule_json: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, default=dict
    )
    metric_inclusion_rule_json: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, default=dict
    )
    version_token: Mapped[str] = mapped_column(String(64), nullable=False)
    effective_from: Mapped[date] = mapped_column(Date, nullable=False)
    effective_to: Mapped[date | None] = mapped_column(Date, nullable=True)
    supersedes_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("board_pack_section_definitions.id", ondelete="RESTRICT"),
        nullable=True,
    )
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="candidate")
    created_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)


class NarrativeTemplate(FinancialBase):
    __tablename__ = "narrative_templates"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "organisation_id",
            "template_code",
            "version_token",
            name="uq_narrative_templates_version_token",
        ),
        CheckConstraint(
            "template_type IN ('executive_summary_template','metric_commentary_template','variance_commentary_template','risk_commentary_template','anomaly_commentary_template','board_attention_template','period_close_summary_template')",
            name="ck_narrative_templates_type",
        ),
        CheckConstraint(
            "status IN ('candidate','active','superseded','rejected')",
            name="ck_narrative_templates_status",
        ),
        Index(
            "idx_narrative_templates_lookup",
            "tenant_id",
            "organisation_id",
            "template_code",
            "effective_from",
            "created_at",
        ),
        Index(
            "uq_narrative_templates_one_active",
            "tenant_id",
            "organisation_id",
            "template_code",
            unique=True,
            postgresql_where=text("status = 'active'"),
        ),
    )

    organisation_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    template_code: Mapped[str] = mapped_column(String(128), nullable=False)
    template_name: Mapped[str] = mapped_column(String(255), nullable=False)
    template_type: Mapped[str] = mapped_column(String(64), nullable=False)
    template_text: Mapped[str] = mapped_column(Text, nullable=False)
    template_body_json: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    placeholder_schema_json: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, default=dict
    )
    version_token: Mapped[str] = mapped_column(String(64), nullable=False)
    effective_from: Mapped[date] = mapped_column(Date, nullable=False)
    effective_to: Mapped[date | None] = mapped_column(Date, nullable=True)
    supersedes_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("narrative_templates.id", ondelete="RESTRICT"),
        nullable=True,
    )
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="candidate")
    created_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)


class BoardPackInclusionRule(FinancialBase):
    __tablename__ = "board_pack_inclusion_rules"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "organisation_id",
            "rule_code",
            "version_token",
            name="uq_board_pack_inclusion_rules_version_token",
        ),
        CheckConstraint(
            "rule_type IN ('material_variance_only','high_critical_risks','sustained_anomalies','top_severity_issues','conditional_section')",
            name="ck_board_pack_inclusion_rules_type",
        ),
        CheckConstraint(
            "status IN ('candidate','active','superseded','rejected')",
            name="ck_board_pack_inclusion_rules_status",
        ),
        Index(
            "idx_board_pack_inclusion_rules_lookup",
            "tenant_id",
            "organisation_id",
            "rule_code",
            "effective_from",
            "created_at",
        ),
        Index(
            "uq_board_pack_inclusion_rules_one_active",
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
    rule_type: Mapped[str] = mapped_column(String(64), nullable=False)
    inclusion_logic_json: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    version_token: Mapped[str] = mapped_column(String(64), nullable=False)
    effective_from: Mapped[date] = mapped_column(Date, nullable=False)
    effective_to: Mapped[date | None] = mapped_column(Date, nullable=True)
    supersedes_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("board_pack_inclusion_rules.id", ondelete="RESTRICT"),
        nullable=True,
    )
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="candidate")
    created_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)


class BoardPackRun(FinancialBase):
    __tablename__ = "board_pack_runs"
    __table_args__ = (
        UniqueConstraint("tenant_id", "run_token", name="uq_board_pack_runs_tenant_token"),
        CheckConstraint(
            "status IN ('created','running','completed','failed')",
            name="ck_board_pack_runs_status",
        ),
        CheckConstraint(
            "jsonb_typeof(source_metric_run_ids_json) = 'array' AND jsonb_array_length(source_metric_run_ids_json) > 0",
            name="ck_board_pack_runs_metric_sources_required",
        ),
        CheckConstraint(
            "jsonb_typeof(source_risk_run_ids_json) = 'array' AND jsonb_array_length(source_risk_run_ids_json) > 0",
            name="ck_board_pack_runs_risk_sources_required",
        ),
        CheckConstraint(
            "jsonb_typeof(source_anomaly_run_ids_json) = 'array' AND jsonb_array_length(source_anomaly_run_ids_json) > 0",
            name="ck_board_pack_runs_anomaly_sources_required",
        ),
        Index(
            "idx_board_pack_runs_lookup",
            "tenant_id",
            "organisation_id",
            "reporting_period",
            "created_at",
        ),
        Index("idx_board_pack_runs_token", "tenant_id", "run_token", unique=True),
    )

    organisation_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    reporting_period: Mapped[date] = mapped_column(Date, nullable=False)
    board_pack_definition_version_token: Mapped[str] = mapped_column(String(64), nullable=False)
    section_definition_version_token: Mapped[str] = mapped_column(String(64), nullable=False)
    narrative_template_version_token: Mapped[str] = mapped_column(String(64), nullable=False)
    inclusion_rule_version_token: Mapped[str] = mapped_column(String(64), nullable=False)
    source_metric_run_ids_json: Mapped[list[str]] = mapped_column(
        JSONB, nullable=False, default=list
    )
    source_risk_run_ids_json: Mapped[list[str]] = mapped_column(
        JSONB, nullable=False, default=list
    )
    source_anomaly_run_ids_json: Mapped[list[str]] = mapped_column(
        JSONB, nullable=False, default=list
    )
    run_token: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="created")
    validation_summary_json: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, default=dict
    )
    created_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)


class BoardPackResult(FinancialBase):
    __tablename__ = "board_pack_results"
    __table_args__ = (
        UniqueConstraint("run_id", name="uq_board_pack_results_run_id"),
        CheckConstraint(
            "overall_health_classification IN ('healthy','watch','stressed','critical')",
            name="ck_board_pack_results_health",
        ),
        CheckConstraint(
            "status IN ('generated','finalized','failed')",
            name="ck_board_pack_results_status",
        ),
        Index("idx_board_pack_results_run", "tenant_id", "run_id", "created_at"),
    )

    run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("board_pack_runs.id", ondelete="RESTRICT"),
        nullable=False,
    )
    board_pack_code: Mapped[str] = mapped_column(String(128), nullable=False)
    reporting_period: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="generated")
    executive_summary_text: Mapped[str] = mapped_column(Text, nullable=False)
    overall_health_classification: Mapped[str] = mapped_column(String(32), nullable=False)
    created_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)


class BoardPackSectionResult(FinancialBase):
    __tablename__ = "board_pack_section_results"
    __table_args__ = (
        UniqueConstraint(
            "run_id",
            "section_order",
            name="uq_board_pack_section_results_order",
        ),
        Index("idx_board_pack_section_results_run", "tenant_id", "run_id", "section_order"),
    )

    run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("board_pack_runs.id", ondelete="RESTRICT"),
        nullable=False,
    )
    section_code: Mapped[str] = mapped_column(String(128), nullable=False)
    section_order: Mapped[int] = mapped_column(Integer, nullable=False)
    section_title: Mapped[str] = mapped_column(String(255), nullable=False)
    section_summary_text: Mapped[str] = mapped_column(Text, nullable=False)
    section_payload_json: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    created_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)


class BoardPackNarrativeBlock(FinancialBase):
    __tablename__ = "board_pack_narrative_blocks"
    __table_args__ = (
        UniqueConstraint(
            "section_result_id",
            "block_order",
            name="uq_board_pack_narrative_blocks_order",
        ),
        Index(
            "idx_board_pack_narrative_blocks_run",
            "tenant_id",
            "run_id",
            "section_result_id",
            "block_order",
        ),
    )

    run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("board_pack_runs.id", ondelete="RESTRICT"),
        nullable=False,
    )
    section_result_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("board_pack_section_results.id", ondelete="RESTRICT"),
        nullable=False,
    )
    narrative_template_code: Mapped[str] = mapped_column(String(128), nullable=False)
    narrative_text: Mapped[str] = mapped_column(Text, nullable=False)
    narrative_payload_json: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, default=dict
    )
    block_order: Mapped[int] = mapped_column(Integer, nullable=False)
    created_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)


class BoardPackEvidenceLink(FinancialBase):
    __tablename__ = "board_pack_evidence_links"
    __table_args__ = (
        CheckConstraint(
            "evidence_type IN ('metric_result','variance_result','trend_result','risk_result','anomaly_result','reconciliation_result','normalized_source_ref','narrative_template','definition_token','run_input')",
            name="ck_board_pack_evidence_links_type",
        ),
        Index(
            "idx_board_pack_evidence_links_run",
            "tenant_id",
            "run_id",
            "created_at",
        ),
        Index(
            "idx_board_pack_evidence_links_section",
            "tenant_id",
            "run_id",
            "section_result_id",
        ),
    )

    run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("board_pack_runs.id", ondelete="RESTRICT"),
        nullable=False,
    )
    section_result_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("board_pack_section_results.id", ondelete="RESTRICT"),
        nullable=True,
    )
    narrative_block_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("board_pack_narrative_blocks.id", ondelete="RESTRICT"),
        nullable=True,
    )
    evidence_type: Mapped[str] = mapped_column(String(64), nullable=False)
    evidence_ref: Mapped[str] = mapped_column(Text, nullable=False)
    evidence_label: Mapped[str] = mapped_column(String(255), nullable=False)
    evidence_payload_json: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, default=dict
    )
    board_attention_flag: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    severity_rank: Mapped[Decimal] = mapped_column(Numeric(12, 6), nullable=False, default=Decimal("0"))
    created_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
