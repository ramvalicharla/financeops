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


class EntityHierarchy(FinancialBase):
    __tablename__ = "entity_hierarchies"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "organisation_id",
            "hierarchy_code",
            "version_token",
            name="uq_entity_hierarchies_version_token",
        ),
        CheckConstraint(
            "hierarchy_type IN ('legal','management','custom')",
            name="ck_entity_hierarchies_type",
        ),
        CheckConstraint(
            "status IN ('candidate','active','superseded','rejected')",
            name="ck_entity_hierarchies_status",
        ),
        Index(
            "idx_entity_hierarchies_lookup",
            "tenant_id",
            "organisation_id",
            "hierarchy_code",
            "effective_from",
            "created_at",
        ),
        Index(
            "uq_entity_hierarchies_one_active",
            "tenant_id",
            "organisation_id",
            "hierarchy_code",
            unique=True,
            postgresql_where=text("status = 'active'"),
        ),
    )

    organisation_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    hierarchy_code: Mapped[str] = mapped_column(String(128), nullable=False)
    hierarchy_name: Mapped[str] = mapped_column(String(255), nullable=False)
    hierarchy_type: Mapped[str] = mapped_column(String(64), nullable=False)
    version_token: Mapped[str] = mapped_column(String(64), nullable=False)
    effective_from: Mapped[date] = mapped_column(Date, nullable=False)
    effective_to: Mapped[date | None] = mapped_column(Date, nullable=True)
    supersedes_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("entity_hierarchies.id", ondelete="RESTRICT"),
        nullable=True,
    )
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="candidate")
    created_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)


class EntityHierarchyNode(FinancialBase):
    __tablename__ = "entity_hierarchy_nodes"
    __table_args__ = (
        CheckConstraint("node_level >= 0", name="ck_entity_hierarchy_nodes_level"),
        CheckConstraint(
            "status IN ('candidate','active','superseded','rejected')",
            name="ck_entity_hierarchy_nodes_status",
        ),
        Index(
            "idx_entity_hierarchy_nodes_lookup",
            "tenant_id",
            "hierarchy_id",
            "entity_id",
            "node_level",
            "created_at",
        ),
        Index(
            "uq_entity_hierarchy_nodes_one_active",
            "tenant_id",
            "hierarchy_id",
            "entity_id",
            unique=True,
            postgresql_where=text("status = 'active'"),
        ),
        Index(
            "idx_entity_hierarchy_nodes_parent",
            "tenant_id",
            "hierarchy_id",
            "parent_node_id",
        ),
    )

    hierarchy_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("entity_hierarchies.id", ondelete="RESTRICT"),
        nullable=False,
    )
    entity_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    parent_node_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("entity_hierarchy_nodes.id", ondelete="RESTRICT"),
        nullable=True,
    )
    node_level: Mapped[int] = mapped_column(Integer, nullable=False)
    effective_from: Mapped[date] = mapped_column(Date, nullable=False)
    effective_to: Mapped[date | None] = mapped_column(Date, nullable=True)
    supersedes_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("entity_hierarchy_nodes.id", ondelete="RESTRICT"),
        nullable=True,
    )
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="candidate")
    created_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)


class ConsolidationScope(FinancialBase):
    __tablename__ = "consolidation_scopes"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "organisation_id",
            "scope_code",
            "version_token",
            name="uq_consolidation_scopes_version_token",
        ),
        CheckConstraint(
            "status IN ('candidate','active','superseded','rejected')",
            name="ck_consolidation_scopes_status",
        ),
        Index(
            "idx_consolidation_scopes_lookup",
            "tenant_id",
            "organisation_id",
            "scope_code",
            "effective_from",
            "created_at",
        ),
        Index(
            "uq_consolidation_scopes_one_active",
            "tenant_id",
            "organisation_id",
            "scope_code",
            unique=True,
            postgresql_where=text("status = 'active'"),
        ),
    )

    organisation_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    scope_code: Mapped[str] = mapped_column(String(128), nullable=False)
    scope_name: Mapped[str] = mapped_column(String(255), nullable=False)
    hierarchy_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("entity_hierarchies.id", ondelete="RESTRICT"),
        nullable=False,
    )
    scope_selector_json: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    version_token: Mapped[str] = mapped_column(String(64), nullable=False)
    effective_from: Mapped[date] = mapped_column(Date, nullable=False)
    effective_to: Mapped[date | None] = mapped_column(Date, nullable=True)
    supersedes_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("consolidation_scopes.id", ondelete="RESTRICT"),
        nullable=True,
    )
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="candidate")
    created_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)


class ConsolidationRuleDefinition(FinancialBase):
    __tablename__ = "consolidation_rule_definitions"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "organisation_id",
            "rule_code",
            "version_token",
            name="uq_consolidation_rule_definitions_version_token",
        ),
        CheckConstraint(
            "rule_type IN ('aggregation_rule','inclusion_rule','intercompany_rule','adjustment_rule','ownership_placeholder','currency_placeholder')",
            name="ck_consolidation_rule_definitions_type",
        ),
        CheckConstraint(
            "status IN ('candidate','active','superseded','rejected')",
            name="ck_consolidation_rule_definitions_status",
        ),
        Index(
            "idx_consolidation_rule_definitions_lookup",
            "tenant_id",
            "organisation_id",
            "rule_code",
            "effective_from",
            "created_at",
        ),
        Index(
            "uq_consolidation_rule_definitions_one_active",
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
    version_token: Mapped[str] = mapped_column(String(64), nullable=False)
    effective_from: Mapped[date] = mapped_column(Date, nullable=False)
    effective_to: Mapped[date | None] = mapped_column(Date, nullable=True)
    supersedes_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("consolidation_rule_definitions.id", ondelete="RESTRICT"),
        nullable=True,
    )
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="candidate")
    created_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)


class IntercompanyMappingRule(FinancialBase):
    __tablename__ = "intercompany_mapping_rules"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "organisation_id",
            "rule_code",
            "version_token",
            name="uq_intercompany_mapping_rules_version_token",
        ),
        CheckConstraint(
            "status IN ('candidate','active','superseded','rejected')",
            name="ck_intercompany_mapping_rules_status",
        ),
        Index(
            "idx_intercompany_mapping_rules_lookup",
            "tenant_id",
            "organisation_id",
            "rule_code",
            "effective_from",
            "created_at",
        ),
        Index(
            "uq_intercompany_mapping_rules_one_active",
            "tenant_id",
            "organisation_id",
            "rule_code",
            unique=True,
            postgresql_where=text("status = 'active'"),
        ),
    )

    organisation_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    rule_code: Mapped[str] = mapped_column(String(128), nullable=False)
    source_selector_json: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    counterpart_selector_json: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, default=dict
    )
    treatment_rule_json: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    version_token: Mapped[str] = mapped_column(String(64), nullable=False)
    effective_from: Mapped[date] = mapped_column(Date, nullable=False)
    effective_to: Mapped[date | None] = mapped_column(Date, nullable=True)
    supersedes_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("intercompany_mapping_rules.id", ondelete="RESTRICT"),
        nullable=True,
    )
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="candidate")
    created_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)


class ConsolidationAdjustmentDefinition(FinancialBase):
    __tablename__ = "consolidation_adjustment_definitions"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "organisation_id",
            "adjustment_code",
            "version_token",
            name="uq_consolidation_adjustment_definitions_version_token",
        ),
        CheckConstraint(
            "adjustment_type IN ('analytic_adjustment','intercompany_placeholder','manual_grouping','presentation_reclass')",
            name="ck_consolidation_adjustment_definitions_type",
        ),
        CheckConstraint(
            "status IN ('candidate','active','superseded','rejected')",
            name="ck_consolidation_adjustment_definitions_status",
        ),
        Index(
            "idx_consolidation_adjustment_definitions_lookup",
            "tenant_id",
            "organisation_id",
            "adjustment_code",
            "effective_from",
            "created_at",
        ),
        Index(
            "uq_consolidation_adjustment_definitions_one_active",
            "tenant_id",
            "organisation_id",
            "adjustment_code",
            unique=True,
            postgresql_where=text("status = 'active'"),
        ),
    )

    organisation_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    adjustment_code: Mapped[str] = mapped_column(String(128), nullable=False)
    adjustment_name: Mapped[str] = mapped_column(String(255), nullable=False)
    adjustment_type: Mapped[str] = mapped_column(String(64), nullable=False)
    logic_json: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    version_token: Mapped[str] = mapped_column(String(64), nullable=False)
    effective_from: Mapped[date] = mapped_column(Date, nullable=False)
    effective_to: Mapped[date | None] = mapped_column(Date, nullable=True)
    supersedes_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("consolidation_adjustment_definitions.id", ondelete="RESTRICT"),
        nullable=True,
    )
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="candidate")
    created_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)


class MultiEntityConsolidationRun(FinancialBase):
    __tablename__ = "multi_entity_consolidation_runs"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "run_token",
            name="uq_multi_entity_consolidation_runs_tenant_token",
        ),
        CheckConstraint(
            "run_status IN ('created','running','completed','failed')",
            name="ck_multi_entity_consolidation_runs_status",
        ),
        CheckConstraint(
            "jsonb_typeof(source_run_refs_json) = 'array' AND jsonb_array_length(source_run_refs_json) > 0",
            name="ck_multi_entity_consolidation_runs_sources_required",
        ),
        Index(
            "idx_multi_entity_consolidation_runs_lookup",
            "tenant_id",
            "organisation_id",
            "reporting_period",
            "created_at",
        ),
        Index(
            "idx_multi_entity_consolidation_runs_token",
            "tenant_id",
            "run_token",
            unique=True,
        ),
    )

    organisation_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    reporting_period: Mapped[date] = mapped_column(Date, nullable=False)
    hierarchy_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("entity_hierarchies.id", ondelete="RESTRICT"),
        nullable=False,
    )
    scope_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("consolidation_scopes.id", ondelete="RESTRICT"),
        nullable=False,
    )
    hierarchy_version_token: Mapped[str] = mapped_column(String(64), nullable=False)
    scope_version_token: Mapped[str] = mapped_column(String(64), nullable=False)
    rule_version_token: Mapped[str] = mapped_column(String(64), nullable=False)
    intercompany_version_token: Mapped[str] = mapped_column(String(64), nullable=False)
    adjustment_version_token: Mapped[str] = mapped_column(String(64), nullable=False)
    source_run_refs_json: Mapped[list[dict[str, Any]]] = mapped_column(
        JSONB, nullable=False, default=list
    )
    run_token: Mapped[str] = mapped_column(String(64), nullable=False)
    run_status: Mapped[str] = mapped_column(String(32), nullable=False, default="created")
    validation_summary_json: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, default=dict
    )
    created_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)


class MultiEntityConsolidationMetricResult(FinancialBase):
    __tablename__ = "multi_entity_consolidation_metric_results"
    __table_args__ = (
        UniqueConstraint(
            "run_id",
            "line_no",
            name="uq_multi_entity_consolidation_metric_results_line_no",
        ),
        CheckConstraint(
            "entity_count >= 1",
            name="ck_multi_entity_consolidation_metric_results_entity_count",
        ),
        Index(
            "idx_multi_entity_consolidation_metric_results_run",
            "tenant_id",
            "run_id",
            "line_no",
        ),
        Index(
            "idx_multi_entity_consolidation_metric_results_metric",
            "tenant_id",
            "run_id",
            "metric_code",
        ),
    )

    run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("multi_entity_consolidation_runs.id", ondelete="RESTRICT"),
        nullable=False,
    )
    line_no: Mapped[int] = mapped_column(Integer, nullable=False)
    metric_code: Mapped[str] = mapped_column(String(128), nullable=False)
    scope_json: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    currency_code: Mapped[str] = mapped_column(String(3), nullable=False)
    aggregated_value: Mapped[Decimal] = mapped_column(Numeric(20, 6), nullable=False)
    entity_count: Mapped[int] = mapped_column(Integer, nullable=False)
    materiality_flag: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)


class MultiEntityConsolidationVarianceResult(FinancialBase):
    __tablename__ = "multi_entity_consolidation_variance_results"
    __table_args__ = (
        UniqueConstraint(
            "run_id",
            "line_no",
            name="uq_multi_entity_consolidation_variance_results_line_no",
        ),
        CheckConstraint(
            "comparison_type IN ('mom','yoy','actual_vs_budget','actual_vs_forecast')",
            name="ck_multi_entity_consolidation_variance_results_type",
        ),
        Index(
            "idx_multi_entity_consolidation_variance_results_run",
            "tenant_id",
            "run_id",
            "line_no",
        ),
        Index(
            "idx_multi_entity_consolidation_variance_results_metric",
            "tenant_id",
            "run_id",
            "metric_code",
        ),
    )

    run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("multi_entity_consolidation_runs.id", ondelete="RESTRICT"),
        nullable=False,
    )
    line_no: Mapped[int] = mapped_column(Integer, nullable=False)
    metric_code: Mapped[str] = mapped_column(String(128), nullable=False)
    comparison_type: Mapped[str] = mapped_column(String(32), nullable=False)
    base_value: Mapped[Decimal] = mapped_column(Numeric(20, 6), nullable=False)
    current_value: Mapped[Decimal] = mapped_column(Numeric(20, 6), nullable=False)
    variance_value: Mapped[Decimal] = mapped_column(Numeric(20, 6), nullable=False)
    variance_pct: Mapped[Decimal | None] = mapped_column(Numeric(20, 6), nullable=True)
    materiality_flag: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)


class MultiEntityConsolidationEvidenceLink(FinancialBase):
    __tablename__ = "multi_entity_consolidation_evidence_links"
    __table_args__ = (
        CheckConstraint(
            "evidence_type IN ('entity_metric_result','entity_variance_result','intercompany_decision','adjustment_reference','hierarchy_version','scope_version','rule_version','source_run_ref')",
            name="ck_multi_entity_consolidation_evidence_links_type",
        ),
        Index(
            "idx_multi_entity_consolidation_evidence_links_run",
            "tenant_id",
            "run_id",
            "created_at",
        ),
        Index(
            "idx_multi_entity_consolidation_evidence_links_metric",
            "tenant_id",
            "run_id",
            "metric_result_id",
        ),
    )

    run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("multi_entity_consolidation_runs.id", ondelete="RESTRICT"),
        nullable=False,
    )
    metric_result_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("multi_entity_consolidation_metric_results.id", ondelete="RESTRICT"),
        nullable=True,
    )
    variance_result_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("multi_entity_consolidation_variance_results.id", ondelete="RESTRICT"),
        nullable=True,
    )
    evidence_type: Mapped[str] = mapped_column(String(64), nullable=False)
    evidence_ref: Mapped[str] = mapped_column(Text, nullable=False)
    evidence_label: Mapped[str] = mapped_column(String(255), nullable=False)
    evidence_payload_json: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    created_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
