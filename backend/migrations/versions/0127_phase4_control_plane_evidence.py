"""phase4 control plane evidence

Revision ID: 0127_phase4_control_plane
Revises: 0126_phase3_1_wc_linkage
Create Date: 2026-04-10 00:10:00.000000

"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0127_phase4_control_plane"
down_revision: Union[str, None] = "0126_phase3_1_wc_linkage"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "governance_snapshots",
        sa.Column("entity_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("module_key", sa.String(length=64), nullable=False),
        sa.Column("snapshot_kind", sa.String(length=64), nullable=False),
        sa.Column("subject_type", sa.String(length=64), nullable=False),
        sa.Column("subject_id", sa.String(length=128), nullable=False),
        sa.Column("version_no", sa.Integer(), nullable=False),
        sa.Column("determinism_hash", sa.String(length=64), nullable=False),
        sa.Column("replay_supported", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("payload_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("comparison_payload_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("trigger_event", sa.String(length=64), nullable=True),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("snapshot_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False, server_default=sa.text("gen_random_uuid()")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("chain_hash", sa.String(length=64), nullable=False),
        sa.Column("previous_hash", sa.String(length=64), nullable=False),
        sa.ForeignKeyConstraint(["entity_id"], ["cp_entities.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "tenant_id",
            "subject_type",
            "subject_id",
            "version_no",
            name="uq_governance_snapshots_subject_version",
        ),
    )
    op.create_index("ix_governance_snapshots_tenant_id", "governance_snapshots", ["tenant_id"])
    op.create_index(
        "ix_governance_snapshots_subject",
        "governance_snapshots",
        ["tenant_id", "subject_type", "subject_id", "created_at"],
    )
    op.create_index(
        "ix_governance_snapshots_hash",
        "governance_snapshots",
        ["tenant_id", "determinism_hash", "created_at"],
    )

    op.create_table(
        "governance_snapshot_inputs",
        sa.Column("snapshot_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("input_type", sa.String(length=64), nullable=False),
        sa.Column("input_ref", sa.Text(), nullable=False),
        sa.Column("input_hash", sa.String(length=64), nullable=True),
        sa.Column("input_payload_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False, server_default=sa.text("gen_random_uuid()")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("chain_hash", sa.String(length=64), nullable=False),
        sa.Column("previous_hash", sa.String(length=64), nullable=False),
        sa.ForeignKeyConstraint(["snapshot_id"], ["governance_snapshots.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_governance_snapshot_inputs_tenant_id", "governance_snapshot_inputs", ["tenant_id"])
    op.create_index(
        "ix_governance_snapshot_inputs_snapshot",
        "governance_snapshot_inputs",
        ["tenant_id", "snapshot_id", "created_at"],
    )
    op.create_index(
        "ix_governance_snapshot_inputs_ref",
        "governance_snapshot_inputs",
        ["tenant_id", "input_type", "input_ref"],
    )

    op.create_table(
        "governance_snapshot_metadata",
        sa.Column("snapshot_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("metadata_key", sa.String(length=128), nullable=False),
        sa.Column("metadata_value_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False, server_default=sa.text("gen_random_uuid()")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("chain_hash", sa.String(length=64), nullable=False),
        sa.Column("previous_hash", sa.String(length=64), nullable=False),
        sa.ForeignKeyConstraint(["snapshot_id"], ["governance_snapshots.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_governance_snapshot_metadata_tenant_id", "governance_snapshot_metadata", ["tenant_id"])
    op.create_index(
        "ix_governance_snapshot_metadata_snapshot",
        "governance_snapshot_metadata",
        ["tenant_id", "snapshot_id", "created_at"],
    )
    op.create_index(
        "ix_governance_snapshot_metadata_key",
        "governance_snapshot_metadata",
        ["tenant_id", "metadata_key", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_governance_snapshot_metadata_key", table_name="governance_snapshot_metadata")
    op.drop_index("ix_governance_snapshot_metadata_snapshot", table_name="governance_snapshot_metadata")
    op.drop_index("ix_governance_snapshot_metadata_tenant_id", table_name="governance_snapshot_metadata")
    op.drop_table("governance_snapshot_metadata")

    op.drop_index("ix_governance_snapshot_inputs_ref", table_name="governance_snapshot_inputs")
    op.drop_index("ix_governance_snapshot_inputs_snapshot", table_name="governance_snapshot_inputs")
    op.drop_index("ix_governance_snapshot_inputs_tenant_id", table_name="governance_snapshot_inputs")
    op.drop_table("governance_snapshot_inputs")

    op.drop_index("ix_governance_snapshots_hash", table_name="governance_snapshots")
    op.drop_index("ix_governance_snapshots_subject", table_name="governance_snapshots")
    op.drop_index("ix_governance_snapshots_tenant_id", table_name="governance_snapshots")
    op.drop_table("governance_snapshots")
