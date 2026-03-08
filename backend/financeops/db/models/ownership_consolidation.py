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


class OwnershipStructureDefinition(FinancialBase):
    __tablename__ = "ownership_structure_definitions"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "organisation_id",
            "ownership_structure_code",
            "version_token",
            name="uq_ownership_structure_definitions_version_token",
        ),
        CheckConstraint(
            "ownership_basis_type IN ('equity_percentage','voting_percentage','manual_control')",
            name="ck_ownership_structure_definitions_basis_type",
        ),
        CheckConstraint(
            "status IN ('candidate','active','superseded','rejected')",
            name="ck_ownership_structure_definitions_status",
        ),
        Index(
            "idx_ownership_structure_definitions_lookup",
            "tenant_id",
            "organisation_id",
            "ownership_structure_code",
            "effective_from",
            "created_at",
        ),
        Index(
            "uq_ownership_structure_definitions_one_active",
            "tenant_id",
            "organisation_id",
            "ownership_structure_code",
            unique=True,
            postgresql_where=text("status = 'active'"),
        ),
    )

    organisation_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    ownership_structure_code: Mapped[str] = mapped_column(String(128), nullable=False)
    ownership_structure_name: Mapped[str] = mapped_column(String(255), nullable=False)
    hierarchy_scope_ref: Mapped[str] = mapped_column(String(128), nullable=False)
    ownership_basis_type: Mapped[str] = mapped_column(String(64), nullable=False)
    version_token: Mapped[str] = mapped_column(String(64), nullable=False)
    effective_from: Mapped[date] = mapped_column(Date, nullable=False)
    effective_to: Mapped[date | None] = mapped_column(Date, nullable=True)
    supersedes_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("ownership_structure_definitions.id", ondelete="RESTRICT"),
        nullable=True,
    )
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="candidate")
    created_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)


class OwnershipRelationship(FinancialBase):
    __tablename__ = "ownership_relationships"
    __table_args__ = (
        CheckConstraint(
            "ownership_percentage >= 0 AND ownership_percentage <= 100",
            name="ck_ownership_relationships_pct",
        ),
        CheckConstraint(
            "voting_percentage_nullable IS NULL OR (voting_percentage_nullable >= 0 AND voting_percentage_nullable <= 100)",
            name="ck_ownership_relationships_voting_pct",
        ),
        CheckConstraint(
            "status IN ('candidate','active','superseded','rejected')",
            name="ck_ownership_relationships_status",
        ),
        Index(
            "idx_ownership_relationships_lookup",
            "tenant_id",
            "organisation_id",
            "ownership_structure_id",
            "parent_entity_id",
            "child_entity_id",
            "effective_from",
            "created_at",
        ),
        Index(
            "uq_ownership_relationships_one_active",
            "tenant_id",
            "ownership_structure_id",
            "parent_entity_id",
            "child_entity_id",
            unique=True,
            postgresql_where=text("status = 'active'"),
        ),
        Index(
            "idx_ownership_relationships_child_lookup",
            "tenant_id",
            "ownership_structure_id",
            "child_entity_id",
            "created_at",
        ),
    )

    organisation_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    ownership_structure_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("ownership_structure_definitions.id", ondelete="RESTRICT"),
        nullable=False,
    )
    parent_entity_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    child_entity_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    ownership_percentage: Mapped[Decimal] = mapped_column(Numeric(9, 6), nullable=False)
    voting_percentage_nullable: Mapped[Decimal | None] = mapped_column(Numeric(9, 6), nullable=True)
    control_indicator: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    minority_interest_indicator: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    proportionate_consolidation_indicator: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )
    effective_from: Mapped[date] = mapped_column(Date, nullable=False)
    effective_to: Mapped[date | None] = mapped_column(Date, nullable=True)
    supersedes_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("ownership_relationships.id", ondelete="RESTRICT"),
        nullable=True,
    )
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="candidate")
    created_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)


class OwnershipConsolidationRuleDefinition(FinancialBase):
    __tablename__ = "ownership_consolidation_rule_definitions"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "organisation_id",
            "rule_code",
            "version_token",
            name="uq_ownership_consolidation_rule_definitions_version_token",
        ),
        CheckConstraint(
            "rule_type IN ('full_consolidation_rule','proportionate_consolidation_rule','minority_interest_rule','equity_attribution_placeholder','ownership_exclusion_rule')",
            name="ck_ownership_consolidation_rule_definitions_type",
        ),
        CheckConstraint(
            "status IN ('candidate','active','superseded','rejected')",
            name="ck_ownership_consolidation_rule_definitions_status",
        ),
        Index(
            "idx_ownership_consolidation_rule_definitions_lookup",
            "tenant_id",
            "organisation_id",
            "rule_code",
            "effective_from",
            "created_at",
        ),
        Index(
            "uq_ownership_consolidation_rule_definitions_one_active",
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
    rule_logic_json: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    attribution_policy_json: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, default=dict
    )
    version_token: Mapped[str] = mapped_column(String(64), nullable=False)
    effective_from: Mapped[date] = mapped_column(Date, nullable=False)
    effective_to: Mapped[date | None] = mapped_column(Date, nullable=True)
    supersedes_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("ownership_consolidation_rule_definitions.id", ondelete="RESTRICT"),
        nullable=True,
    )
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="candidate")
    created_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)


class MinorityInterestRuleDefinition(FinancialBase):
    __tablename__ = "minority_interest_rule_definitions"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "organisation_id",
            "rule_code",
            "version_token",
            name="uq_minority_interest_rule_definitions_version_token",
        ),
        CheckConstraint(
            "attribution_basis_type IN ('ownership_share','voting_share','explicit_policy')",
            name="ck_minority_interest_rule_definitions_basis_type",
        ),
        CheckConstraint(
            "status IN ('candidate','active','superseded','rejected')",
            name="ck_minority_interest_rule_definitions_status",
        ),
        Index(
            "idx_minority_interest_rule_definitions_lookup",
            "tenant_id",
            "organisation_id",
            "rule_code",
            "effective_from",
            "created_at",
        ),
        Index(
            "uq_minority_interest_rule_definitions_one_active",
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
    attribution_basis_type: Mapped[str] = mapped_column(String(64), nullable=False)
    calculation_logic_json: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    presentation_logic_json: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, default=dict
    )
    version_token: Mapped[str] = mapped_column(String(64), nullable=False)
    effective_from: Mapped[date] = mapped_column(Date, nullable=False)
    effective_to: Mapped[date | None] = mapped_column(Date, nullable=True)
    supersedes_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("minority_interest_rule_definitions.id", ondelete="RESTRICT"),
        nullable=True,
    )
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="candidate")
    created_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)


class OwnershipConsolidationRun(FinancialBase):
    __tablename__ = "ownership_consolidation_runs"
    __table_args__ = (
        UniqueConstraint("tenant_id", "run_token", name="uq_ownership_consolidation_runs_tenant_token"),
        CheckConstraint(
            "run_status IN ('created','running','completed','failed')",
            name="ck_ownership_consolidation_runs_status",
        ),
        CheckConstraint(
            "jsonb_typeof(source_consolidation_run_refs_json) = 'array' AND jsonb_array_length(source_consolidation_run_refs_json) > 0",
            name="ck_ownership_consolidation_runs_sources_required",
        ),
        Index(
            "idx_ownership_consolidation_runs_lookup",
            "tenant_id",
            "organisation_id",
            "reporting_period",
            "created_at",
        ),
        Index("idx_ownership_consolidation_runs_token", "tenant_id", "run_token", unique=True),
    )

    organisation_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    reporting_period: Mapped[date] = mapped_column(Date, nullable=False)
    hierarchy_version_token: Mapped[str] = mapped_column(String(64), nullable=False)
    scope_version_token: Mapped[str] = mapped_column(String(64), nullable=False)
    ownership_structure_version_token: Mapped[str] = mapped_column(String(64), nullable=False)
    ownership_rule_version_token: Mapped[str] = mapped_column(String(64), nullable=False)
    minority_interest_rule_version_token: Mapped[str] = mapped_column(String(64), nullable=False)
    fx_translation_run_ref_nullable: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("fx_translation_runs.id", ondelete="RESTRICT"),
        nullable=True,
    )
    source_consolidation_run_refs_json: Mapped[list[dict[str, Any]]] = mapped_column(
        JSONB, nullable=False, default=list
    )
    run_token: Mapped[str] = mapped_column(String(64), nullable=False)
    run_status: Mapped[str] = mapped_column(String(32), nullable=False, default="created")
    validation_summary_json: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, default=dict
    )
    created_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)


class OwnershipConsolidationMetricResult(FinancialBase):
    __tablename__ = "ownership_consolidation_metric_results"
    __table_args__ = (
        UniqueConstraint(
            "ownership_consolidation_run_id",
            "line_no",
            name="uq_ownership_consolidation_metric_results_line_no",
        ),
        Index(
            "idx_ownership_consolidation_metric_results_run",
            "tenant_id",
            "ownership_consolidation_run_id",
            "line_no",
        ),
        Index(
            "idx_ownership_consolidation_metric_results_metric",
            "tenant_id",
            "ownership_consolidation_run_id",
            "metric_code",
        ),
    )

    ownership_consolidation_run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("ownership_consolidation_runs.id", ondelete="RESTRICT"),
        nullable=False,
    )
    line_no: Mapped[int] = mapped_column(Integer, nullable=False)
    scope_code: Mapped[str] = mapped_column(String(128), nullable=False)
    metric_code: Mapped[str] = mapped_column(String(128), nullable=False)
    source_consolidated_value: Mapped[Decimal] = mapped_column(Numeric(20, 6), nullable=False)
    ownership_weight_applied: Mapped[Decimal] = mapped_column(Numeric(9, 6), nullable=False)
    attributed_value: Mapped[Decimal] = mapped_column(Numeric(20, 6), nullable=False)
    minority_interest_value_nullable: Mapped[Decimal | None] = mapped_column(Numeric(20, 6), nullable=True)
    reporting_currency_code_nullable: Mapped[str | None] = mapped_column(String(3), nullable=True)
    lineage_summary_json: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    created_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)


class OwnershipConsolidationVarianceResult(FinancialBase):
    __tablename__ = "ownership_consolidation_variance_results"
    __table_args__ = (
        UniqueConstraint(
            "ownership_consolidation_run_id",
            "line_no",
            name="uq_ownership_consolidation_variance_results_line_no",
        ),
        CheckConstraint(
            "variance_code IN ('mom','yoy','actual_vs_budget','actual_vs_forecast')",
            name="ck_ownership_consolidation_variance_results_type",
        ),
        Index(
            "idx_ownership_consolidation_variance_results_run",
            "tenant_id",
            "ownership_consolidation_run_id",
            "line_no",
        ),
        Index(
            "idx_ownership_consolidation_variance_results_metric",
            "tenant_id",
            "ownership_consolidation_run_id",
            "metric_code",
        ),
    )

    ownership_consolidation_run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("ownership_consolidation_runs.id", ondelete="RESTRICT"),
        nullable=False,
    )
    line_no: Mapped[int] = mapped_column(Integer, nullable=False)
    scope_code: Mapped[str] = mapped_column(String(128), nullable=False)
    metric_code: Mapped[str] = mapped_column(String(128), nullable=False)
    variance_code: Mapped[str] = mapped_column(String(64), nullable=False)
    source_current_value: Mapped[Decimal] = mapped_column(Numeric(20, 6), nullable=False)
    source_comparison_value: Mapped[Decimal] = mapped_column(Numeric(20, 6), nullable=False)
    ownership_weight_applied: Mapped[Decimal] = mapped_column(Numeric(9, 6), nullable=False)
    attributed_current_value: Mapped[Decimal] = mapped_column(Numeric(20, 6), nullable=False)
    attributed_comparison_value: Mapped[Decimal] = mapped_column(Numeric(20, 6), nullable=False)
    attributed_variance_abs: Mapped[Decimal] = mapped_column(Numeric(20, 6), nullable=False)
    attributed_variance_pct: Mapped[Decimal | None] = mapped_column(Numeric(20, 6), nullable=True)
    attributed_variance_bps: Mapped[Decimal | None] = mapped_column(Numeric(20, 6), nullable=True)
    minority_interest_value_nullable: Mapped[Decimal | None] = mapped_column(Numeric(20, 6), nullable=True)
    lineage_summary_json: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    created_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)


class OwnershipConsolidationEvidenceLink(FinancialBase):
    __tablename__ = "ownership_consolidation_evidence_links"
    __table_args__ = (
        CheckConstraint(
            "evidence_type IN ('source_metric_result','source_variance_result','ownership_relationship','ownership_rule_version','minority_interest_rule_version','fx_translation_run_ref')",
            name="ck_ownership_consolidation_evidence_links_type",
        ),
        Index(
            "idx_ownership_consolidation_evidence_links_run",
            "tenant_id",
            "ownership_consolidation_run_id",
            "created_at",
        ),
    )

    ownership_consolidation_run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("ownership_consolidation_runs.id", ondelete="RESTRICT"),
        nullable=False,
    )
    metric_result_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("ownership_consolidation_metric_results.id", ondelete="RESTRICT"),
        nullable=True,
    )
    variance_result_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("ownership_consolidation_variance_results.id", ondelete="RESTRICT"),
        nullable=True,
    )
    evidence_type: Mapped[str] = mapped_column(String(64), nullable=False)
    evidence_ref: Mapped[str] = mapped_column(Text, nullable=False)
    evidence_label: Mapped[str] = mapped_column(String(255), nullable=False)
    evidence_payload_json: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    created_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
