from __future__ import annotations

import uuid
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from financeops.db.base import FinancialBase


class ReconciliationSession(FinancialBase):
    __tablename__ = "reconciliation_sessions"
    __table_args__ = (
        UniqueConstraint("session_token", name="uq_reconciliation_sessions_token"),
        CheckConstraint(
            "status IN ('created','running','completed','failed')",
            name="ck_reconciliation_sessions_status",
        ),
        Index("idx_recon_session_tenant", "tenant_id", "created_at"),
        Index("idx_recon_session_token", "session_token", unique=True),
    )

    organisation_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    reconciliation_type: Mapped[str] = mapped_column(String(64), nullable=False)
    source_a_type: Mapped[str] = mapped_column(String(64), nullable=False)
    source_a_ref: Mapped[str] = mapped_column(Text, nullable=False)
    source_b_type: Mapped[str] = mapped_column(String(64), nullable=False)
    source_b_ref: Mapped[str] = mapped_column(Text, nullable=False)
    period_start: Mapped[Any] = mapped_column(Date, nullable=False)
    period_end: Mapped[Any] = mapped_column(Date, nullable=False)
    matching_rule_version: Mapped[str] = mapped_column(String(64), nullable=False)
    tolerance_rule_version: Mapped[str] = mapped_column(String(64), nullable=False)
    session_token: Mapped[str] = mapped_column(String(64), nullable=False)
    materiality_config_json: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, default=dict
    )
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="created")
    created_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)


class ReconciliationScope(FinancialBase):
    __tablename__ = "reconciliation_scopes"
    __table_args__ = (
        UniqueConstraint(
            "session_id", "scope_code", name="uq_reconciliation_scopes_session_scope_code"
        ),
        Index("idx_reconciliation_scopes_session", "tenant_id", "session_id"),
    )

    session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("reconciliation_sessions.id", ondelete="CASCADE"),
        nullable=False,
    )
    scope_code: Mapped[str] = mapped_column(String(64), nullable=False)
    scope_label: Mapped[str] = mapped_column(String(255), nullable=False)
    scope_json: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    created_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)


class ReconciliationLine(FinancialBase):
    __tablename__ = "reconciliation_lines"
    __table_args__ = (
        UniqueConstraint(
            "session_id", "line_key", name="uq_reconciliation_lines_session_line_key"
        ),
        CheckConstraint(
            "reconciliation_status IN ('matched','exception','review_required')",
            name="ck_reconciliation_lines_status",
        ),
        CheckConstraint(
            "difference_type IN "
            "('missing_in_a','missing_in_b','value_mismatch','mapping_gap',"
            "'timing_difference','classification_difference','fx_difference',"
            "'aggregation_difference','none')",
            name="ck_reconciliation_lines_difference_type",
        ),
        Index("idx_recon_lines_session", "tenant_id", "session_id"),
        Index("idx_recon_lines_status", "tenant_id", "session_id", "reconciliation_status"),
        Index("idx_recon_lines_difference_type", "tenant_id", "session_id", "difference_type"),
        Index("idx_recon_lines_line_key", "tenant_id", "session_id", "line_key"),
    )

    entity_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("cp_entities.id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
        comment="Entity scope for multi-entity tenants",
    )
    session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("reconciliation_sessions.id", ondelete="CASCADE"),
        nullable=False,
    )
    scope_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("reconciliation_scopes.id", ondelete="SET NULL"),
        nullable=True,
    )
    line_key: Mapped[str] = mapped_column(String(128), nullable=False)
    comparison_dimension_json: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, default=dict
    )
    source_a_value: Mapped[Decimal] = mapped_column(Numeric(20, 6), nullable=False)
    source_b_value: Mapped[Decimal] = mapped_column(Numeric(20, 6), nullable=False)
    variance_value: Mapped[Decimal] = mapped_column(Numeric(20, 6), nullable=False)
    variance_abs: Mapped[Decimal] = mapped_column(Numeric(20, 6), nullable=False)
    variance_pct: Mapped[Decimal] = mapped_column(Numeric(20, 6), nullable=False)
    currency_code: Mapped[str] = mapped_column(String(3), nullable=False)
    reconciliation_status: Mapped[str] = mapped_column(String(32), nullable=False)
    difference_type: Mapped[str] = mapped_column(String(64), nullable=False)
    materiality_flag: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    explanation_hint: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)


class ReconciliationException(FinancialBase):
    __tablename__ = "reconciliation_exceptions"
    __table_args__ = (
        CheckConstraint(
            "severity IN ('info','warning','error')",
            name="ck_reconciliation_exceptions_severity",
        ),
        CheckConstraint(
            "resolution_status IN ('open','resolved','reopened','accepted')",
            name="ck_reconciliation_exceptions_resolution_status",
        ),
        Index("idx_recon_exception_by_session", "tenant_id", "session_id", "created_at"),
    )

    entity_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("cp_entities.id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
        comment="Entity scope for multi-entity tenants",
    )
    session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("reconciliation_sessions.id", ondelete="CASCADE"),
        nullable=False,
    )
    line_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("reconciliation_lines.id", ondelete="CASCADE"),
        nullable=False,
    )
    exception_code: Mapped[str] = mapped_column(String(64), nullable=False)
    severity: Mapped[str] = mapped_column(String(16), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    owner_role: Mapped[str | None] = mapped_column(String(64), nullable=True)
    resolution_status: Mapped[str] = mapped_column(String(32), nullable=False, default="open")
    created_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)


class ReconciliationResolutionEvent(FinancialBase):
    __tablename__ = "reconciliation_resolution_events"
    __table_args__ = (
        CheckConstraint(
            "event_type IN ("
            "'exception_opened','explanation_added','evidence_linked','assigned',"
            "'accepted_timing_difference','accepted_mapping_gap','escalated',"
            "'resolved','reopened'"
            ")",
            name="ck_reconciliation_resolution_events_event_type",
        ),
        Index("idx_recon_resolution_event_by_line", "tenant_id", "line_id", "created_at"),
        Index("idx_recon_resolution_event_by_session", "tenant_id", "session_id", "created_at"),
    )

    session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("reconciliation_sessions.id", ondelete="CASCADE"),
        nullable=False,
    )
    line_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("reconciliation_lines.id", ondelete="CASCADE"),
        nullable=False,
    )
    exception_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("reconciliation_exceptions.id", ondelete="SET NULL"),
        nullable=True,
    )
    event_type: Mapped[str] = mapped_column(String(64), nullable=False)
    event_payload_json: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, default=dict
    )
    actor_user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)


class ReconciliationEvidenceLink(FinancialBase):
    __tablename__ = "reconciliation_evidence_links"
    __table_args__ = (
        CheckConstraint(
            "evidence_type IN ("
            "'mis_snapshot_line','tb_line','gl_entry','schedule_row',"
            "'far_depreciation_row','lease_liability_row','uploaded_artifact'"
            ")",
            name="ck_reconciliation_evidence_links_evidence_type",
        ),
        Index("idx_recon_evidence_by_line", "tenant_id", "line_id", "created_at"),
        Index("idx_recon_evidence_by_session", "tenant_id", "session_id", "created_at"),
    )

    session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("reconciliation_sessions.id", ondelete="CASCADE"),
        nullable=False,
    )
    line_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("reconciliation_lines.id", ondelete="CASCADE"),
        nullable=False,
    )
    evidence_type: Mapped[str] = mapped_column(String(64), nullable=False)
    evidence_ref: Mapped[str] = mapped_column(Text, nullable=False)
    evidence_label: Mapped[str] = mapped_column(String(255), nullable=False)
    created_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
