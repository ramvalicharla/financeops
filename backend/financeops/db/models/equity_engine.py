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


class EquityStatementDefinition(FinancialBase):
    __tablename__ = "equity_statement_definitions"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "organisation_id",
            "statement_code",
            "version_token",
            name="uq_equity_statement_definitions_version_token",
        ),
        CheckConstraint(
            "reporting_currency_basis IN ('source_currency','reporting_currency')",
            name="ck_equity_statement_definitions_currency_basis",
        ),
        CheckConstraint(
            "status IN ('candidate','active','superseded','rejected')",
            name="ck_equity_statement_definitions_status",
        ),
        Index(
            "idx_equity_statement_definitions_lookup",
            "tenant_id",
            "organisation_id",
            "statement_code",
            "effective_from",
            "created_at",
        ),
        Index(
            "uq_equity_statement_definitions_one_active",
            "tenant_id",
            "organisation_id",
            "statement_code",
            unique=True,
            postgresql_where=text("status = 'active'"),
        ),
    )

    organisation_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    statement_code: Mapped[str] = mapped_column(String(128), nullable=False)
    statement_name: Mapped[str] = mapped_column(String(255), nullable=False)
    reporting_currency_basis: Mapped[str] = mapped_column(String(32), nullable=False)
    ownership_basis_flag: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    version_token: Mapped[str] = mapped_column(String(64), nullable=False)
    effective_from: Mapped[date] = mapped_column(Date, nullable=False)
    effective_to: Mapped[date | None] = mapped_column(Date, nullable=True)
    supersedes_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("equity_statement_definitions.id", ondelete="RESTRICT"),
        nullable=True,
    )
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="candidate")
    created_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)


class EquityLineDefinition(FinancialBase):
    __tablename__ = "equity_line_definitions"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "organisation_id",
            "statement_definition_id",
            "line_code",
            "version_token",
            name="uq_equity_line_definitions_version_token",
        ),
        CheckConstraint("presentation_order >= 1", name="ck_equity_line_definitions_order"),
        CheckConstraint(
            "line_type IN ('share_capital','share_premium','retained_earnings','other_reserves','oci_accumulated','cta_reserve','minority_interest','total_equity')",
            name="ck_equity_line_definitions_line_type",
        ),
        CheckConstraint(
            "status IN ('candidate','active','superseded','rejected')",
            name="ck_equity_line_definitions_status",
        ),
        Index(
            "idx_equity_line_definitions_lookup",
            "tenant_id",
            "organisation_id",
            "statement_definition_id",
            "presentation_order",
            "effective_from",
            "created_at",
        ),
        Index(
            "uq_equity_line_definitions_one_active",
            "tenant_id",
            "organisation_id",
            "statement_definition_id",
            "line_code",
            unique=True,
            postgresql_where=text("status = 'active'"),
        ),
    )

    organisation_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    statement_definition_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("equity_statement_definitions.id", ondelete="RESTRICT"),
        nullable=False,
    )
    line_code: Mapped[str] = mapped_column(String(128), nullable=False)
    line_name: Mapped[str] = mapped_column(String(255), nullable=False)
    line_type: Mapped[str] = mapped_column(String(64), nullable=False)
    presentation_order: Mapped[int] = mapped_column(Integer, nullable=False)
    rollforward_required_flag: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    version_token: Mapped[str] = mapped_column(String(64), nullable=False)
    effective_from: Mapped[date] = mapped_column(Date, nullable=False)
    effective_to: Mapped[date | None] = mapped_column(Date, nullable=True)
    supersedes_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("equity_line_definitions.id", ondelete="RESTRICT"),
        nullable=True,
    )
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="candidate")
    created_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)


class EquityRollforwardRuleDefinition(FinancialBase):
    __tablename__ = "equity_rollforward_rule_definitions"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "organisation_id",
            "rule_code",
            "version_token",
            name="uq_equity_rollforward_rule_definitions_version_token",
        ),
        CheckConstraint(
            "rule_type IN ('opening_balance_rule','retained_earnings_bridge_rule','oci_accumulation_rule','cta_derivation_rule','ownership_attribution_rule','minority_interest_equity_rule','closing_balance_rule')",
            name="ck_equity_rollforward_rule_definitions_type",
        ),
        CheckConstraint(
            "status IN ('candidate','active','superseded','rejected')",
            name="ck_equity_rollforward_rule_definitions_status",
        ),
        Index(
            "idx_equity_rollforward_rule_definitions_lookup",
            "tenant_id",
            "organisation_id",
            "rule_code",
            "effective_from",
            "created_at",
        ),
        Index(
            "uq_equity_rollforward_rule_definitions_one_active",
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
    source_selector_json: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    derivation_logic_json: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    fx_interaction_logic_json_nullable: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    ownership_interaction_logic_json_nullable: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    version_token: Mapped[str] = mapped_column(String(64), nullable=False)
    effective_from: Mapped[date] = mapped_column(Date, nullable=False)
    effective_to: Mapped[date | None] = mapped_column(Date, nullable=True)
    supersedes_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("equity_rollforward_rule_definitions.id", ondelete="RESTRICT"),
        nullable=True,
    )
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="candidate")
    created_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)


class EquitySourceMapping(FinancialBase):
    __tablename__ = "equity_source_mappings"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "organisation_id",
            "mapping_code",
            "line_code",
            "source_type",
            "version_token",
            name="uq_equity_source_mappings_version_token",
        ),
        CheckConstraint(
            "source_type IN ('consolidation_result','fx_translation_result','ownership_result','pnl_result','adjustment_ref')",
            name="ck_equity_source_mappings_source_type",
        ),
        CheckConstraint(
            "status IN ('candidate','active','superseded','rejected')",
            name="ck_equity_source_mappings_status",
        ),
        Index(
            "idx_equity_source_mappings_lookup",
            "tenant_id",
            "organisation_id",
            "mapping_code",
            "line_code",
            "effective_from",
            "created_at",
        ),
        Index(
            "uq_equity_source_mappings_one_active",
            "tenant_id",
            "organisation_id",
            "mapping_code",
            "line_code",
            "source_type",
            unique=True,
            postgresql_where=text("status = 'active'"),
        ),
    )

    organisation_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    mapping_code: Mapped[str] = mapped_column(String(128), nullable=False)
    line_code: Mapped[str] = mapped_column(String(128), nullable=False)
    source_type: Mapped[str] = mapped_column(String(64), nullable=False)
    source_selector_json: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    transformation_logic_json: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    version_token: Mapped[str] = mapped_column(String(64), nullable=False)
    effective_from: Mapped[date] = mapped_column(Date, nullable=False)
    effective_to: Mapped[date | None] = mapped_column(Date, nullable=True)
    supersedes_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("equity_source_mappings.id", ondelete="RESTRICT"),
        nullable=True,
    )
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="candidate")
    created_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)


class EquityRun(FinancialBase):
    __tablename__ = "equity_runs"
    __table_args__ = (
        UniqueConstraint("tenant_id", "run_token", name="uq_equity_runs_tenant_token"),
        CheckConstraint("run_status IN ('created','running','completed','failed')", name="ck_equity_runs_status"),
        Index("idx_equity_runs_lookup", "tenant_id", "organisation_id", "reporting_period", "created_at"),
    )

    organisation_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    reporting_period: Mapped[date] = mapped_column(Date, nullable=False)
    statement_definition_version_token: Mapped[str] = mapped_column(String(64), nullable=False)
    line_definition_version_token: Mapped[str] = mapped_column(String(64), nullable=False)
    rollforward_rule_version_token: Mapped[str] = mapped_column(String(64), nullable=False)
    source_mapping_version_token: Mapped[str] = mapped_column(String(64), nullable=False)
    consolidation_run_ref_nullable: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("multi_entity_consolidation_runs.id", ondelete="RESTRICT"),
        nullable=True,
    )
    fx_translation_run_ref_nullable: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("fx_translation_runs.id", ondelete="RESTRICT"),
        nullable=True,
    )
    ownership_consolidation_run_ref_nullable: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("ownership_consolidation_runs.id", ondelete="RESTRICT"),
        nullable=True,
    )
    run_token: Mapped[str] = mapped_column(String(64), nullable=False)
    run_status: Mapped[str] = mapped_column(String(32), nullable=False, default="created")
    validation_summary_json: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    created_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)


class EquityLineResult(FinancialBase):
    __tablename__ = "equity_line_results"
    __table_args__ = (
        UniqueConstraint("equity_run_id", "line_no", name="uq_equity_line_results_line_no"),
        Index("idx_equity_line_results_run", "tenant_id", "equity_run_id", "line_no"),
    )

    equity_run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("equity_runs.id", ondelete="RESTRICT"),
        nullable=False,
    )
    line_no: Mapped[int] = mapped_column(Integer, nullable=False)
    line_code: Mapped[str] = mapped_column(String(128), nullable=False)
    opening_balance: Mapped[Decimal] = mapped_column(Numeric(20, 6), nullable=False)
    movement_amount: Mapped[Decimal] = mapped_column(Numeric(20, 6), nullable=False)
    closing_balance: Mapped[Decimal] = mapped_column(Numeric(20, 6), nullable=False)
    source_currency_amount_nullable: Mapped[Decimal | None] = mapped_column(Numeric(20, 6), nullable=True)
    reporting_currency_amount_nullable: Mapped[Decimal | None] = mapped_column(Numeric(20, 6), nullable=True)
    ownership_attributed_amount_nullable: Mapped[Decimal | None] = mapped_column(Numeric(20, 6), nullable=True)
    lineage_summary_json: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    created_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)


class EquityStatementResult(FinancialBase):
    __tablename__ = "equity_statement_results"
    __table_args__ = (
        UniqueConstraint("equity_run_id", name="uq_equity_statement_results_run"),
        Index("idx_equity_statement_results_run", "tenant_id", "equity_run_id"),
    )

    equity_run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("equity_runs.id", ondelete="RESTRICT"),
        nullable=False,
    )
    total_equity_opening: Mapped[Decimal] = mapped_column(Numeric(20, 6), nullable=False)
    total_equity_closing: Mapped[Decimal] = mapped_column(Numeric(20, 6), nullable=False)
    statement_payload_json: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    created_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)


class EquityEvidenceLink(FinancialBase):
    __tablename__ = "equity_evidence_links"
    __table_args__ = (
        CheckConstraint(
            "evidence_type IN ('consolidation_result_ref','fx_translation_run_ref','ownership_run_ref','rule_version_ref','mapping_version_ref','line_mapping_ref')",
            name="ck_equity_evidence_links_type",
        ),
        Index("idx_equity_evidence_links_run", "tenant_id", "equity_run_id", "created_at"),
    )

    equity_run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("equity_runs.id", ondelete="RESTRICT"),
        nullable=False,
    )
    result_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    evidence_type: Mapped[str] = mapped_column(String(64), nullable=False)
    evidence_ref: Mapped[str] = mapped_column(Text, nullable=False)
    evidence_label: Mapped[str] = mapped_column(String(255), nullable=False)
    evidence_payload_json: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    created_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
