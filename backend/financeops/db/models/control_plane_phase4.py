from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from financeops.db.base import FinancialBase


class GovernanceSnapshot(FinancialBase):
    __tablename__ = "governance_snapshots"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "subject_type",
            "subject_id",
            "version_no",
            name="uq_governance_snapshots_subject_version",
        ),
        Index(
            "ix_governance_snapshots_subject",
            "tenant_id",
            "subject_type",
            "subject_id",
            "created_at",
        ),
        Index(
            "ix_governance_snapshots_hash",
            "tenant_id",
            "determinism_hash",
            "created_at",
        ),
    )

    entity_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("cp_entities.id", ondelete="SET NULL"),
        nullable=True,
    )
    module_key: Mapped[str] = mapped_column(String(64), nullable=False)
    snapshot_kind: Mapped[str] = mapped_column(String(64), nullable=False)
    subject_type: Mapped[str] = mapped_column(String(64), nullable=False)
    subject_id: Mapped[str] = mapped_column(String(128), nullable=False)
    version_no: Mapped[int] = mapped_column(Integer, nullable=False)
    determinism_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    replay_supported: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    payload_json: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    comparison_payload_json: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    trigger_event: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    snapshot_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )


class GovernanceSnapshotInput(FinancialBase):
    __tablename__ = "governance_snapshot_inputs"
    __table_args__ = (
        Index("ix_governance_snapshot_inputs_snapshot", "tenant_id", "snapshot_id", "created_at"),
        Index("ix_governance_snapshot_inputs_ref", "tenant_id", "input_type", "input_ref"),
    )

    snapshot_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("governance_snapshots.id", ondelete="RESTRICT"),
        nullable=False,
    )
    input_type: Mapped[str] = mapped_column(String(64), nullable=False)
    input_ref: Mapped[str] = mapped_column(Text, nullable=False)
    input_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    input_payload_json: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    created_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)


class GovernanceSnapshotMetadata(FinancialBase):
    __tablename__ = "governance_snapshot_metadata"
    __table_args__ = (
        Index("ix_governance_snapshot_metadata_snapshot", "tenant_id", "snapshot_id", "created_at"),
        Index("ix_governance_snapshot_metadata_key", "tenant_id", "metadata_key", "created_at"),
    )

    snapshot_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("governance_snapshots.id", ondelete="RESTRICT"),
        nullable=False,
    )
    metadata_key: Mapped[str] = mapped_column(String(128), nullable=False)
    metadata_value_json: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    created_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
