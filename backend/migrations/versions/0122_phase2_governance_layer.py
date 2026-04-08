"""phase2 governance layer foundation

Revision ID: 0122_phase2_governance_layer
Revises: 0121_phase1_intent_pipeline
Create Date: 2026-04-08 18:30:00.000000

"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

from financeops.db.append_only import append_only_function_sql, create_trigger_sql, drop_trigger_sql

revision: str = "0122_phase2_governance_layer"
down_revision: Union[str, None] = "0121_phase1_intent_pipeline"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "airlock_items",
        sa.Column("id", UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("tenant_id", UUID(as_uuid=True), nullable=False),
        sa.Column("entity_id", UUID(as_uuid=True), nullable=True),
        sa.Column("source_type", sa.String(length=64), nullable=False),
        sa.Column("source_reference", sa.String(length=255), nullable=True),
        sa.Column("file_name", sa.String(length=255), nullable=True),
        sa.Column("mime_type", sa.String(length=128), nullable=True),
        sa.Column("size_bytes", sa.Integer(), nullable=True),
        sa.Column("checksum_sha256", sa.String(length=64), nullable=True),
        sa.Column("quarantine_ref", sa.String(length=512), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="RECEIVED"),
        sa.Column("submitted_by_user_id", UUID(as_uuid=True), nullable=False),
        sa.Column("reviewed_by_user_id", UUID(as_uuid=True), nullable=True),
        sa.Column("admitted_by_user_id", UUID(as_uuid=True), nullable=True),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("admitted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("rejected_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("rejection_reason", sa.Text(), nullable=True),
        sa.Column("metadata_json", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("findings_json", JSONB, nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("idempotency_key", sa.String(length=128), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["entity_id"], ["cp_entities.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["submitted_by_user_id"], ["iam_users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["reviewed_by_user_id"], ["iam_users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["admitted_by_user_id"], ["iam_users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "tenant_id",
            "source_type",
            "idempotency_key",
            name="uq_airlock_items_idempotency",
        ),
    )
    op.create_index("ix_airlock_items_tenant_id", "airlock_items", ["tenant_id"])
    op.create_index("ix_airlock_items_lookup", "airlock_items", ["tenant_id", "source_type", "status", "submitted_at"])
    op.create_index("ix_airlock_items_entity", "airlock_items", ["tenant_id", "entity_id", "submitted_at"])

    op.create_table(
        "airlock_events",
        sa.Column("id", UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", UUID(as_uuid=True), nullable=False),
        sa.Column("chain_hash", sa.String(length=64), nullable=False),
        sa.Column("previous_hash", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("airlock_item_id", UUID(as_uuid=True), nullable=False),
        sa.Column("event_type", sa.String(length=64), nullable=False),
        sa.Column("from_status", sa.String(length=32), nullable=True),
        sa.Column("to_status", sa.String(length=32), nullable=True),
        sa.Column("actor_user_id", UUID(as_uuid=True), nullable=True),
        sa.Column("actor_role", sa.String(length=64), nullable=True),
        sa.Column("event_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("event_payload_json", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.ForeignKeyConstraint(["airlock_item_id"], ["airlock_items.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["actor_user_id"], ["iam_users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_airlock_events_tenant_id", "airlock_events", ["tenant_id"])
    op.create_index("ix_airlock_events_item", "airlock_events", ["tenant_id", "airlock_item_id", "created_at"])
    op.create_index("ix_airlock_events_type", "airlock_events", ["tenant_id", "event_type", "created_at"])

    op.create_table(
        "governance_approval_policies",
        sa.Column("id", UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("tenant_id", UUID(as_uuid=True), nullable=False),
        sa.Column("entity_id", UUID(as_uuid=True), nullable=True),
        sa.Column("policy_name", sa.String(length=128), nullable=False),
        sa.Column("module_key", sa.String(length=64), nullable=False),
        sa.Column("mutation_type", sa.String(length=64), nullable=False),
        sa.Column("source_type", sa.String(length=64), nullable=True),
        sa.Column("threshold_amount", sa.Numeric(20, 4), nullable=True),
        sa.Column("required_approver_role", sa.String(length=64), nullable=False),
        sa.Column("approval_mode", sa.String(length=32), nullable=False, server_default="single"),
        sa.Column("active_flag", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("priority", sa.Integer(), nullable=False, server_default="100"),
        sa.Column("policy_payload_json", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_by", UUID(as_uuid=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["entity_id"], ["cp_entities.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_governance_approval_policies_scope",
        "governance_approval_policies",
        ["tenant_id", "module_key", "mutation_type", "active_flag"],
    )
    op.create_index(
        "ix_governance_approval_policies_entity",
        "governance_approval_policies",
        ["tenant_id", "entity_id", "priority"],
    )

    op.create_table(
        "canonical_governance_events",
        sa.Column("id", UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", UUID(as_uuid=True), nullable=False),
        sa.Column("chain_hash", sa.String(length=64), nullable=False),
        sa.Column("previous_hash", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("entity_id", UUID(as_uuid=True), nullable=True),
        sa.Column("module_key", sa.String(length=64), nullable=False),
        sa.Column("subject_type", sa.String(length=64), nullable=False),
        sa.Column("subject_id", sa.String(length=128), nullable=False),
        sa.Column("event_type", sa.String(length=64), nullable=False),
        sa.Column("actor_user_id", UUID(as_uuid=True), nullable=True),
        sa.Column("actor_role", sa.String(length=64), nullable=True),
        sa.Column("payload_json", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.ForeignKeyConstraint(["entity_id"], ["cp_entities.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["actor_user_id"], ["iam_users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_canonical_governance_events_tenant_id", "canonical_governance_events", ["tenant_id"])
    op.create_index(
        "ix_canonical_governance_events_subject",
        "canonical_governance_events",
        ["tenant_id", "subject_type", "subject_id"],
    )
    op.create_index(
        "ix_canonical_governance_events_type",
        "canonical_governance_events",
        ["tenant_id", "event_type", "created_at"],
    )
    op.create_index(
        "ix_canonical_governance_events_module",
        "canonical_governance_events",
        ["tenant_id", "module_key", "created_at"],
    )

    op.add_column("external_sync_runs", sa.Column("source_airlock_item_id", UUID(as_uuid=True), nullable=True))
    op.add_column("external_sync_runs", sa.Column("source_type", sa.String(length=64), nullable=True))
    op.add_column("external_sync_runs", sa.Column("source_external_ref", sa.String(length=255), nullable=True))
    op.create_index("ix_external_sync_runs_source_airlock_item_id", "external_sync_runs", ["source_airlock_item_id"])
    op.create_foreign_key(
        "fk_external_sync_runs_source_airlock_item_id",
        "external_sync_runs",
        "airlock_items",
        ["source_airlock_item_id"],
        ["id"],
        ondelete="SET NULL",
    )

    op.add_column("normalization_runs", sa.Column("source_airlock_item_id", UUID(as_uuid=True), nullable=True))
    op.add_column("normalization_runs", sa.Column("source_type", sa.String(length=64), nullable=True))
    op.add_column("normalization_runs", sa.Column("source_external_ref", sa.String(length=255), nullable=True))
    op.create_index("ix_normalization_runs_source_airlock_item_id", "normalization_runs", ["source_airlock_item_id"])
    op.create_foreign_key(
        "fk_normalization_runs_source_airlock_item_id",
        "normalization_runs",
        "airlock_items",
        ["source_airlock_item_id"],
        ["id"],
        ondelete="SET NULL",
    )

    op.execute(append_only_function_sql())
    for table_name in ("airlock_events", "canonical_governance_events"):
        op.execute(drop_trigger_sql(table_name))
        op.execute(create_trigger_sql(table_name))


def downgrade() -> None:
    for table_name in ("canonical_governance_events", "airlock_events"):
        op.execute(drop_trigger_sql(table_name))

    op.drop_constraint("fk_normalization_runs_source_airlock_item_id", "normalization_runs", type_="foreignkey")
    op.drop_index("ix_normalization_runs_source_airlock_item_id", table_name="normalization_runs")
    op.drop_column("normalization_runs", "source_external_ref")
    op.drop_column("normalization_runs", "source_type")
    op.drop_column("normalization_runs", "source_airlock_item_id")

    op.drop_constraint("fk_external_sync_runs_source_airlock_item_id", "external_sync_runs", type_="foreignkey")
    op.drop_index("ix_external_sync_runs_source_airlock_item_id", table_name="external_sync_runs")
    op.drop_column("external_sync_runs", "source_external_ref")
    op.drop_column("external_sync_runs", "source_type")
    op.drop_column("external_sync_runs", "source_airlock_item_id")

    op.drop_index("ix_canonical_governance_events_module", table_name="canonical_governance_events")
    op.drop_index("ix_canonical_governance_events_type", table_name="canonical_governance_events")
    op.drop_index("ix_canonical_governance_events_subject", table_name="canonical_governance_events")
    op.drop_index("ix_canonical_governance_events_tenant_id", table_name="canonical_governance_events")
    op.drop_table("canonical_governance_events")

    op.drop_index("ix_governance_approval_policies_entity", table_name="governance_approval_policies")
    op.drop_index("ix_governance_approval_policies_scope", table_name="governance_approval_policies")
    op.drop_table("governance_approval_policies")

    op.drop_index("ix_airlock_events_type", table_name="airlock_events")
    op.drop_index("ix_airlock_events_item", table_name="airlock_events")
    op.drop_index("ix_airlock_events_tenant_id", table_name="airlock_events")
    op.drop_table("airlock_events")

    op.drop_index("ix_airlock_items_entity", table_name="airlock_items")
    op.drop_index("ix_airlock_items_lookup", table_name="airlock_items")
    op.drop_index("ix_airlock_items_tenant_id", table_name="airlock_items")
    op.drop_table("airlock_items")
