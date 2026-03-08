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


class CashFlowStatementDefinition(FinancialBase):
    __tablename__ = "cash_flow_statement_definitions"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "organisation_id",
            "definition_code",
            "version_token",
            name="uq_cash_flow_statement_definitions_version_token",
        ),
        CheckConstraint("method_type IN ('indirect','direct')", name="ck_cash_flow_statement_definitions_method_type"),
        CheckConstraint("status IN ('candidate','active','superseded','rejected')", name="ck_cash_flow_statement_definitions_status"),
        Index("idx_cash_flow_statement_definitions_lookup", "tenant_id", "organisation_id", "definition_code", "effective_from", "created_at"),
        Index("uq_cash_flow_statement_definitions_one_active", "tenant_id", "organisation_id", "definition_code", unique=True, postgresql_where=text("status = 'active'")),
    )

    organisation_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    definition_code: Mapped[str] = mapped_column(String(128), nullable=False)
    definition_name: Mapped[str] = mapped_column(String(255), nullable=False)
    method_type: Mapped[str] = mapped_column(String(32), nullable=False)
    layout_json: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    version_token: Mapped[str] = mapped_column(String(64), nullable=False)
    effective_from: Mapped[date] = mapped_column(Date, nullable=False)
    effective_to: Mapped[date | None] = mapped_column(Date, nullable=True)
    supersedes_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("cash_flow_statement_definitions.id", ondelete="RESTRICT"), nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="candidate")
    created_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)


class CashFlowLineMapping(FinancialBase):
    __tablename__ = "cash_flow_line_mappings"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "organisation_id",
            "mapping_code",
            "line_code",
            "version_token",
            name="uq_cash_flow_line_mappings_version_token",
        ),
        CheckConstraint("line_order >= 1", name="ck_cash_flow_line_mappings_line_order"),
        CheckConstraint("method_type IN ('indirect','direct')", name="ck_cash_flow_line_mappings_method_type"),
        CheckConstraint("aggregation_type IN ('sum')", name="ck_cash_flow_line_mappings_aggregation_type"),
        CheckConstraint("ownership_applicability IN ('any','ownership_only','non_ownership_only')", name="ck_cash_flow_line_mappings_ownership_applicability"),
        CheckConstraint("fx_applicability IN ('any','fx_only','non_fx_only')", name="ck_cash_flow_line_mappings_fx_applicability"),
        CheckConstraint("status IN ('candidate','active','superseded','rejected')", name="ck_cash_flow_line_mappings_status"),
        Index("idx_cash_flow_line_mappings_lookup", "tenant_id", "organisation_id", "mapping_code", "line_order", "effective_from", "created_at"),
        Index("uq_cash_flow_line_mappings_one_active", "tenant_id", "organisation_id", "mapping_code", unique=True, postgresql_where=text("status = 'active'")),
    )

    organisation_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    mapping_code: Mapped[str] = mapped_column(String(128), nullable=False)
    line_code: Mapped[str] = mapped_column(String(128), nullable=False)
    line_name: Mapped[str] = mapped_column(String(255), nullable=False)
    section_code: Mapped[str] = mapped_column(String(64), nullable=False)
    line_order: Mapped[int] = mapped_column(Integer, nullable=False)
    method_type: Mapped[str] = mapped_column(String(32), nullable=False)
    source_metric_code: Mapped[str] = mapped_column(String(128), nullable=False)
    sign_multiplier: Mapped[Decimal] = mapped_column(Numeric(9, 6), nullable=False, default=Decimal("1.000000"))
    aggregation_type: Mapped[str] = mapped_column(String(32), nullable=False, default="sum")
    ownership_applicability: Mapped[str] = mapped_column(String(32), nullable=False, default="any")
    fx_applicability: Mapped[str] = mapped_column(String(32), nullable=False, default="any")
    version_token: Mapped[str] = mapped_column(String(64), nullable=False)
    effective_from: Mapped[date] = mapped_column(Date, nullable=False)
    effective_to: Mapped[date | None] = mapped_column(Date, nullable=True)
    supersedes_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("cash_flow_line_mappings.id", ondelete="RESTRICT"), nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="candidate")
    created_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)


class CashFlowBridgeRuleDefinition(FinancialBase):
    __tablename__ = "cash_flow_bridge_rule_definitions"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "organisation_id",
            "rule_code",
            "version_token",
            name="uq_cash_flow_bridge_rule_definitions_version_token",
        ),
        CheckConstraint("status IN ('candidate','active','superseded','rejected')", name="ck_cash_flow_bridge_rule_definitions_status"),
        Index("idx_cash_flow_bridge_rule_definitions_lookup", "tenant_id", "organisation_id", "rule_code", "effective_from", "created_at"),
        Index("uq_cash_flow_bridge_rule_definitions_one_active", "tenant_id", "organisation_id", "rule_code", unique=True, postgresql_where=text("status = 'active'")),
    )

    organisation_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    rule_code: Mapped[str] = mapped_column(String(128), nullable=False)
    rule_name: Mapped[str] = mapped_column(String(255), nullable=False)
    bridge_logic_json: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    ownership_logic_json: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    fx_logic_json: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    version_token: Mapped[str] = mapped_column(String(64), nullable=False)
    effective_from: Mapped[date] = mapped_column(Date, nullable=False)
    effective_to: Mapped[date | None] = mapped_column(Date, nullable=True)
    supersedes_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("cash_flow_bridge_rule_definitions.id", ondelete="RESTRICT"), nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="candidate")
    created_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)


class CashFlowRun(FinancialBase):
    __tablename__ = "cash_flow_runs"
    __table_args__ = (
        UniqueConstraint("tenant_id", "run_token", name="uq_cash_flow_runs_tenant_token"),
        CheckConstraint("run_status IN ('created','running','completed','failed')", name="ck_cash_flow_runs_status"),
        Index("idx_cash_flow_runs_lookup", "tenant_id", "organisation_id", "reporting_period", "created_at"),
        Index("idx_cash_flow_runs_token", "tenant_id", "run_token", unique=True),
    )

    organisation_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    reporting_period: Mapped[date] = mapped_column(Date, nullable=False)
    statement_definition_version_token: Mapped[str] = mapped_column(String(64), nullable=False)
    line_mapping_version_token: Mapped[str] = mapped_column(String(64), nullable=False)
    bridge_rule_version_token: Mapped[str] = mapped_column(String(64), nullable=False)
    source_consolidation_run_ref: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("multi_entity_consolidation_runs.id", ondelete="RESTRICT"), nullable=False)
    source_fx_translation_run_ref_nullable: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("fx_translation_runs.id", ondelete="RESTRICT"), nullable=True)
    source_ownership_consolidation_run_ref_nullable: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("ownership_consolidation_runs.id", ondelete="RESTRICT"), nullable=True)
    run_token: Mapped[str] = mapped_column(String(64), nullable=False)
    run_status: Mapped[str] = mapped_column(String(32), nullable=False, default="created")
    validation_summary_json: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    created_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)


class CashFlowLineResult(FinancialBase):
    __tablename__ = "cash_flow_line_results"
    __table_args__ = (
        UniqueConstraint("run_id", "line_no", name="uq_cash_flow_line_results_line_no"),
        Index("idx_cash_flow_line_results_run", "tenant_id", "run_id", "line_no"),
        Index("idx_cash_flow_line_results_section", "tenant_id", "run_id", "section_code", "line_order"),
    )

    run_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("cash_flow_runs.id", ondelete="RESTRICT"), nullable=False)
    line_no: Mapped[int] = mapped_column(Integer, nullable=False)
    line_code: Mapped[str] = mapped_column(String(128), nullable=False)
    line_name: Mapped[str] = mapped_column(String(255), nullable=False)
    section_code: Mapped[str] = mapped_column(String(64), nullable=False)
    line_order: Mapped[int] = mapped_column(Integer, nullable=False)
    method_type: Mapped[str] = mapped_column(String(32), nullable=False)
    source_metric_code: Mapped[str] = mapped_column(String(128), nullable=False)
    source_value: Mapped[Decimal] = mapped_column(Numeric(20, 6), nullable=False)
    sign_multiplier: Mapped[Decimal] = mapped_column(Numeric(9, 6), nullable=False)
    computed_value: Mapped[Decimal] = mapped_column(Numeric(20, 6), nullable=False)
    currency_code: Mapped[str] = mapped_column(String(3), nullable=False, default="USD")
    ownership_basis_applied: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    fx_basis_applied: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    lineage_summary_json: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    created_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)


class CashFlowEvidenceLink(FinancialBase):
    __tablename__ = "cash_flow_evidence_links"
    __table_args__ = (
        CheckConstraint("evidence_type IN ('source_consolidation_metric','source_fx_metric','source_ownership_metric','line_mapping','bridge_rule','ownership_run_ref','fx_run_ref')", name="ck_cash_flow_evidence_links_type"),
        Index("idx_cash_flow_evidence_links_run", "tenant_id", "run_id", "created_at"),
    )

    run_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("cash_flow_runs.id", ondelete="RESTRICT"), nullable=False)
    line_result_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("cash_flow_line_results.id", ondelete="RESTRICT"), nullable=True)
    evidence_type: Mapped[str] = mapped_column(String(64), nullable=False)
    evidence_ref: Mapped[str] = mapped_column(Text, nullable=False)
    evidence_label: Mapped[str] = mapped_column(String(255), nullable=False)
    evidence_payload_json: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    created_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
