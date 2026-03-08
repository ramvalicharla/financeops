from __future__ import annotations

import uuid
from datetime import date
from typing import Any

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from financeops.db.base import FinancialBase


class ObservabilityRunRegistry(FinancialBase):
    __tablename__ = "observability_run_registry"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "module_code",
            "run_id",
            "run_token",
            name="uq_observability_run_registry_run",
        ),
        CheckConstraint("execution_time_ms >= 0", name="ck_observability_run_registry_execution_time"),
        CheckConstraint(
            "status IN ('discovered','validated','drift_detected','missing_dependency')",
            name="ck_observability_run_registry_status",
        ),
        Index("idx_observability_run_registry_lookup", "tenant_id", "module_code", "created_at"),
        Index("idx_observability_run_registry_run", "tenant_id", "run_id", "created_at"),
    )

    module_code: Mapped[str] = mapped_column(String(64), nullable=False)
    run_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    run_token: Mapped[str] = mapped_column(String(64), nullable=False)
    version_token_snapshot_json: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    upstream_dependencies_json: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, nullable=False, default=list)
    execution_time_ms: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="discovered")
    created_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)


class RunTokenDiffDefinition(FinancialBase):
    __tablename__ = "run_token_diff_definitions"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "comparison_type",
            "version_token",
            name="uq_run_token_diff_definitions_version_token",
        ),
        CheckConstraint(
            "comparison_type IN ('intra_module','cross_module','cross_period')",
            name="ck_run_token_diff_definitions_type",
        ),
        CheckConstraint(
            "status IN ('candidate','active','superseded','rejected')",
            name="ck_run_token_diff_definitions_status",
        ),
        Index(
            "idx_run_token_diff_definitions_lookup",
            "tenant_id",
            "comparison_type",
            "effective_from",
            "created_at",
        ),
        Index(
            "uq_run_token_diff_definitions_one_active",
            "tenant_id",
            "comparison_type",
            unique=True,
            postgresql_where=text("status = 'active'"),
        ),
    )

    comparison_type: Mapped[str] = mapped_column(String(64), nullable=False)
    allowed_modules_json: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    version_token: Mapped[str] = mapped_column(String(64), nullable=False)
    effective_from: Mapped[date] = mapped_column(Date, nullable=False)
    supersedes_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("run_token_diff_definitions.id", ondelete="RESTRICT"),
        nullable=True,
    )
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="candidate")
    created_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)


class RunTokenDiffResult(FinancialBase):
    __tablename__ = "run_token_diff_results"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "base_run_id",
            "compare_run_id",
            "chain_hash",
            name="uq_run_token_diff_results_pair_chain",
        ),
        Index(
            "idx_run_token_diff_results_lookup",
            "tenant_id",
            "base_run_id",
            "compare_run_id",
            "created_at",
        ),
    )

    base_run_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    compare_run_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    diff_summary_json: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    drift_flag: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)


class LineageGraphSnapshot(FinancialBase):
    __tablename__ = "lineage_graph_snapshots"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "root_run_id",
            "deterministic_hash",
            name="uq_lineage_graph_snapshots_hash",
        ),
        Index("idx_lineage_graph_snapshots_lookup", "tenant_id", "root_run_id", "created_at"),
    )

    root_run_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    graph_payload_json: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    deterministic_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    created_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)


class GovernanceEvent(FinancialBase):
    __tablename__ = "governance_events"
    __table_args__ = (
        CheckConstraint(
            "event_type IN ('rule_application_trace','supersession_trace','version_resolution_trace','diff_computed','replay_validated','graph_snapshot_created')",
            name="ck_governance_events_type",
        ),
        Index("idx_governance_events_lookup", "tenant_id", "module_code", "run_id", "created_at"),
    )

    module_code: Mapped[str] = mapped_column(String(64), nullable=False)
    run_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    event_type: Mapped[str] = mapped_column(String(64), nullable=False)
    event_payload_json: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    created_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)


class RunPerformanceMetric(FinancialBase):
    __tablename__ = "run_performance_metrics"
    __table_args__ = (
        CheckConstraint("query_count >= 0", name="ck_run_performance_metrics_query_count"),
        CheckConstraint("execution_time_ms >= 0", name="ck_run_performance_metrics_execution_time"),
        CheckConstraint("dependency_depth >= 0", name="ck_run_performance_metrics_dependency_depth"),
        Index("idx_run_performance_metrics_lookup", "tenant_id", "module_code", "run_id", "created_at"),
    )

    module_code: Mapped[str] = mapped_column(String(64), nullable=False)
    run_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    query_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    execution_time_ms: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    dependency_depth: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)


class ObservabilityRun(FinancialBase):
    __tablename__ = "observability_runs"
    __table_args__ = (
        UniqueConstraint("tenant_id", "operation_token", name="uq_observability_runs_operation_token"),
        CheckConstraint(
            "operation_type IN ('diff','replay_validate','graph_snapshot','dependency_explore','registry_sync')",
            name="ck_observability_runs_type",
        ),
        CheckConstraint("status IN ('created','completed','failed')", name="ck_observability_runs_status"),
        Index("idx_observability_runs_lookup", "tenant_id", "operation_type", "created_at"),
    )

    operation_type: Mapped[str] = mapped_column(String(64), nullable=False)
    input_ref_json: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    operation_token: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="created")
    created_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)


class ObservabilityResult(FinancialBase):
    __tablename__ = "observability_results"
    __table_args__ = (
        Index("idx_observability_results_lookup", "tenant_id", "observability_run_id", "created_at"),
    )

    observability_run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("observability_runs.id", ondelete="RESTRICT"),
        nullable=False,
    )
    result_payload_json: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    created_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)


class ObservabilityEvidenceLink(FinancialBase):
    __tablename__ = "observability_evidence_links"
    __table_args__ = (
        CheckConstraint(
            "evidence_type IN ('upstream_run','diff_result','graph_snapshot','governance_event','performance_metric')",
            name="ck_observability_evidence_links_type",
        ),
        Index("idx_observability_evidence_links_lookup", "tenant_id", "observability_run_id", "created_at"),
    )

    observability_run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("observability_runs.id", ondelete="RESTRICT"),
        nullable=False,
    )
    result_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("observability_results.id", ondelete="RESTRICT"),
        nullable=True,
    )
    evidence_type: Mapped[str] = mapped_column(String(64), nullable=False)
    evidence_ref: Mapped[str] = mapped_column(Text, nullable=False)
    evidence_label: Mapped[str] = mapped_column(String(255), nullable=False)
    evidence_payload_json: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    created_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
