from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import Date, DateTime, ForeignKey, Index, Integer, Numeric, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from financeops.db.base import FinancialBase


class ConsolidationRun(FinancialBase):
    __tablename__ = "consolidation_runs"
    __table_args__ = (
        UniqueConstraint("tenant_id", "request_signature", name="uq_consol_runs_tenant_signature"),
        Index("idx_consol_runs_tenant_period", "tenant_id", "period_year", "period_month"),
        Index("idx_consol_runs_tenant_created", "tenant_id", "created_at"),
    )

    period_year: Mapped[int] = mapped_column(Integer, nullable=False)
    period_month: Mapped[int] = mapped_column(Integer, nullable=False)
    parent_currency: Mapped[str] = mapped_column(String(3), nullable=False)
    initiated_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    request_signature: Mapped[str] = mapped_column(String(64), nullable=False)
    configuration_json: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    workflow_id: Mapped[str] = mapped_column(String(128), nullable=False)
    correlation_id: Mapped[str | None] = mapped_column(String(64), nullable=True)


class ConsolidationRunEvent(FinancialBase):
    __tablename__ = "consolidation_run_events"
    __table_args__ = (
        UniqueConstraint("run_id", "event_seq", name="uq_consol_run_events_seq"),
        UniqueConstraint(
            "run_id",
            "event_type",
            "idempotency_key",
            name="uq_consol_run_events_idempotent",
        ),
        Index("idx_consol_run_events_tenant_run", "tenant_id", "run_id", "event_seq"),
    )

    run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("consolidation_runs.id", ondelete="CASCADE"),
        nullable=False,
    )
    event_seq: Mapped[int] = mapped_column(Integer, nullable=False)
    event_type: Mapped[str] = mapped_column(String(64), nullable=False)
    event_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False)
    metadata_json: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    correlation_id: Mapped[str | None] = mapped_column(String(64), nullable=True)


class ConsolidationEntity(FinancialBase):
    __tablename__ = "consolidation_entities"
    __table_args__ = (
        UniqueConstraint("tenant_id", "run_id", "entity_id", name="uq_consol_entities_run_entity"),
        Index("idx_consol_entities_tenant_run", "tenant_id", "run_id"),
    )

    run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("consolidation_runs.id", ondelete="CASCADE"),
        nullable=False,
    )
    entity_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    entity_currency: Mapped[str] = mapped_column(String(3), nullable=False)
    source_snapshot_reference: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("normalized_financial_snapshots.snapshot_id", ondelete="RESTRICT"),
        nullable=False,
    )
    expected_rate: Mapped[Decimal | None] = mapped_column(Numeric(20, 6), nullable=True)
    correlation_id: Mapped[str | None] = mapped_column(String(64), nullable=True)


class ConsolidationLineItem(FinancialBase):
    __tablename__ = "consolidation_line_items"
    __table_args__ = (
        UniqueConstraint("run_id", "snapshot_line_id", name="uq_consol_lines_snapshot"),
        Index("idx_consol_lines_tenant_run", "tenant_id", "run_id"),
        Index("idx_consol_lines_account", "tenant_id", "run_id", "account_code"),
    )

    run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("consolidation_runs.id", ondelete="CASCADE"),
        nullable=False,
    )
    entity_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    snapshot_line_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("normalized_financial_snapshot_lines.snapshot_line_id", ondelete="RESTRICT"),
        nullable=False,
    )
    account_code: Mapped[str] = mapped_column(String(64), nullable=False)
    local_currency: Mapped[str] = mapped_column(String(3), nullable=False)
    local_amount: Mapped[Decimal] = mapped_column(Numeric(20, 6), nullable=False)
    fx_rate_used: Mapped[Decimal] = mapped_column(Numeric(20, 6), nullable=False)
    expected_rate: Mapped[Decimal] = mapped_column(Numeric(20, 6), nullable=False)
    parent_amount: Mapped[Decimal] = mapped_column(Numeric(20, 6), nullable=False)
    fx_delta_component: Mapped[Decimal] = mapped_column(Numeric(20, 6), nullable=False)
    ic_reference: Mapped[str | None] = mapped_column(String(255), nullable=True)
    ic_counterparty_entity: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    transaction_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    correlation_id: Mapped[str | None] = mapped_column(String(64), nullable=True)


class IntercompanyPair(FinancialBase):
    __tablename__ = "intercompany_pairs"
    __table_args__ = (
        UniqueConstraint("run_id", "match_key_hash", name="uq_intercompany_pairs_match_key"),
        Index("idx_ic_pairs_tenant_run", "tenant_id", "run_id"),
        Index("idx_ic_pairs_classification", "tenant_id", "run_id", "classification"),
    )

    run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("consolidation_runs.id", ondelete="CASCADE"),
        nullable=False,
    )
    match_key_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    entity_from: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    entity_to: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    account_code: Mapped[str] = mapped_column(String(64), nullable=False)
    ic_reference: Mapped[str | None] = mapped_column(String(255), nullable=True)
    amount_local_from: Mapped[Decimal] = mapped_column(Numeric(20, 6), nullable=False)
    amount_local_to: Mapped[Decimal] = mapped_column(Numeric(20, 6), nullable=False)
    amount_parent_from: Mapped[Decimal] = mapped_column(Numeric(20, 6), nullable=False)
    amount_parent_to: Mapped[Decimal] = mapped_column(Numeric(20, 6), nullable=False)
    expected_difference: Mapped[Decimal] = mapped_column(Numeric(20, 6), nullable=False)
    actual_difference: Mapped[Decimal] = mapped_column(Numeric(20, 6), nullable=False)
    fx_explained: Mapped[Decimal] = mapped_column(Numeric(20, 6), nullable=False)
    unexplained_difference: Mapped[Decimal] = mapped_column(Numeric(20, 6), nullable=False)
    classification: Mapped[str] = mapped_column(String(64), nullable=False)
    correlation_id: Mapped[str | None] = mapped_column(String(64), nullable=True)


class ConsolidationElimination(FinancialBase):
    __tablename__ = "consolidation_eliminations"
    __table_args__ = (
        Index("idx_consol_elims_tenant_run", "tenant_id", "run_id"),
        Index("idx_consol_elims_status", "tenant_id", "run_id", "elimination_status"),
    )

    run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("consolidation_runs.id", ondelete="CASCADE"),
        nullable=False,
    )
    intercompany_pair_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("intercompany_pairs.id", ondelete="CASCADE"),
        nullable=False,
    )
    entity_from: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    entity_to: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    account_code: Mapped[str] = mapped_column(String(64), nullable=False)
    classification_at_time: Mapped[str] = mapped_column(String(64), nullable=False)
    elimination_status: Mapped[str] = mapped_column(String(32), nullable=False)
    eliminated_amount_parent: Mapped[Decimal] = mapped_column(Numeric(20, 6), nullable=False)
    fx_component_impact_parent: Mapped[Decimal] = mapped_column(Numeric(20, 6), nullable=False)
    residual_difference_parent: Mapped[Decimal] = mapped_column(Numeric(20, 6), nullable=False)
    rule_code: Mapped[str] = mapped_column(String(64), nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    correlation_id: Mapped[str | None] = mapped_column(String(64), nullable=True)


class ConsolidationResult(FinancialBase):
    __tablename__ = "consolidation_results"
    __table_args__ = (
        UniqueConstraint("run_id", "consolidated_account_code", name="uq_consol_results_account"),
        Index("idx_consol_results_tenant_run", "tenant_id", "run_id"),
    )

    run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("consolidation_runs.id", ondelete="CASCADE"),
        nullable=False,
    )
    consolidated_account_code: Mapped[str] = mapped_column(String(64), nullable=False)
    consolidated_amount_parent: Mapped[Decimal] = mapped_column(Numeric(20, 6), nullable=False)
    fx_impact_total: Mapped[Decimal] = mapped_column(Numeric(20, 6), nullable=False)
    correlation_id: Mapped[str | None] = mapped_column(String(64), nullable=True)


class NormalizedFinancialSnapshot(FinancialBase):
    __tablename__ = "normalized_financial_snapshots"
    __table_args__ = (
        Index("idx_norm_snapshots_tenant_period", "tenant_id", "period_year", "period_month"),
        Index("idx_norm_snapshots_entity", "tenant_id", "entity_id"),
        Index("idx_norm_snapshots_type", "tenant_id", "snapshot_type"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        "snapshot_id",
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    entity_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    period_year: Mapped[int] = mapped_column(Integer, nullable=False)
    period_month: Mapped[int] = mapped_column(Integer, nullable=False)
    snapshot_type: Mapped[str] = mapped_column(String(64), nullable=False, default="normalized_pnl_v1")
    entity_currency: Mapped[str] = mapped_column(String(3), nullable=False)
    produced_by_module: Mapped[str] = mapped_column(String(64), nullable=False)
    source_artifact_reference: Mapped[str] = mapped_column(String(255), nullable=False)
    supersedes_snapshot_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("normalized_financial_snapshots.snapshot_id", ondelete="SET NULL"),
        nullable=True,
    )
    correlation_id: Mapped[str | None] = mapped_column(String(64), nullable=True)


class NormalizedFinancialSnapshotLine(FinancialBase):
    __tablename__ = "normalized_financial_snapshot_lines"
    __table_args__ = (
        Index("idx_norm_snapshot_lines_tenant_snapshot", "tenant_id", "snapshot_id"),
        Index("idx_norm_snapshot_lines_account", "tenant_id", "snapshot_id", "account_code"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        "snapshot_line_id",
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    snapshot_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("normalized_financial_snapshots.snapshot_id", ondelete="CASCADE"),
        nullable=False,
    )
    account_code: Mapped[str] = mapped_column(String(64), nullable=False)
    local_amount: Mapped[Decimal] = mapped_column(Numeric(20, 6), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    ic_reference: Mapped[str | None] = mapped_column(String(255), nullable=True)
    counterparty_entity: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    transaction_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    ic_account_class: Mapped[str | None] = mapped_column(String(64), nullable=True)
    correlation_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
