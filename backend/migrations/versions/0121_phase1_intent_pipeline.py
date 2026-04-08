"""phase1 intent pipeline foundation

Revision ID: 0121_phase1_intent_pipeline
Revises: 0120_normalize_iam_user_emails
Create Date: 2026-04-08 12:00:00.000000

"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

from financeops.db.append_only import append_only_function_sql, create_trigger_sql, drop_trigger_sql

revision: str = "0121_phase1_intent_pipeline"
down_revision: Union[str, None] = "0120_normalize_iam_user_emails"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "canonical_intents",
        sa.Column("id", UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("tenant_id", UUID(as_uuid=True), nullable=False),
        sa.Column("org_id", UUID(as_uuid=True), nullable=False),
        sa.Column("entity_id", UUID(as_uuid=True), nullable=False),
        sa.Column("intent_type", sa.String(length=64), nullable=False),
        sa.Column("module_key", sa.String(length=64), nullable=False),
        sa.Column("target_type", sa.String(length=64), nullable=False),
        sa.Column("target_id", UUID(as_uuid=True), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="DRAFT"),
        sa.Column("requested_by_user_id", UUID(as_uuid=True), nullable=False),
        sa.Column("requested_by_role", sa.String(length=64), nullable=False),
        sa.Column("requested_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("validated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("executed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("recorded_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("rejected_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("rejection_reason", sa.Text(), nullable=True),
        sa.Column("payload_json", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("guard_results_json", JSONB, nullable=True),
        sa.Column("record_refs_json", JSONB, nullable=True),
        sa.Column("approval_policy_id", UUID(as_uuid=True), nullable=True),
        sa.Column("job_id", UUID(as_uuid=True), nullable=True),
        sa.Column("idempotency_key", sa.String(length=128), nullable=False),
        sa.Column("source_channel", sa.String(length=16), nullable=False, server_default="api"),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["org_id"], ["cp_organisations.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["entity_id"], ["cp_entities.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["requested_by_user_id"], ["iam_users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "tenant_id",
            "intent_type",
            "entity_id",
            "idempotency_key",
            name="uq_canonical_intents_idempotency",
        ),
    )
    op.create_index("ix_canonical_intents_tenant_id", "canonical_intents", ["tenant_id"])
    op.create_index("ix_canonical_intents_org_id", "canonical_intents", ["org_id"])
    op.create_index("ix_canonical_intents_entity_id", "canonical_intents", ["entity_id"])
    op.create_index("ix_canonical_intents_target_id", "canonical_intents", ["target_id"])
    op.create_index("ix_canonical_intents_job_id", "canonical_intents", ["job_id"])
    op.create_index(
        "ix_canonical_intents_lookup",
        "canonical_intents",
        ["tenant_id", "intent_type", "status"],
    )

    op.create_table(
        "canonical_jobs",
        sa.Column("id", UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("intent_id", UUID(as_uuid=True), nullable=False),
        sa.Column("job_type", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="PENDING"),
        sa.Column("runner_type", sa.String(length=32), nullable=False, server_default="INLINE"),
        sa.Column("queue_name", sa.String(length=128), nullable=False),
        sa.Column("idempotency_key", sa.String(length=128), nullable=False),
        sa.Column("requested_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("failed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("retry_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("max_retries", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("error_code", sa.String(length=64), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("error_details_json", JSONB, nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["intent_id"], ["canonical_intents.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("intent_id", name="uq_canonical_jobs_intent_id"),
    )
    op.create_index("ix_canonical_jobs_intent_id", "canonical_jobs", ["intent_id"])
    op.create_index("ix_canonical_jobs_lookup", "canonical_jobs", ["status", "runner_type"])

    op.create_table(
        "canonical_intent_events",
        sa.Column("id", UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", UUID(as_uuid=True), nullable=False),
        sa.Column("chain_hash", sa.String(length=64), nullable=False),
        sa.Column("previous_hash", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("intent_id", UUID(as_uuid=True), nullable=False),
        sa.Column("event_type", sa.String(length=64), nullable=False),
        sa.Column("from_status", sa.String(length=32), nullable=True),
        sa.Column("to_status", sa.String(length=32), nullable=True),
        sa.Column("actor_user_id", UUID(as_uuid=True), nullable=True),
        sa.Column("actor_role", sa.String(length=64), nullable=True),
        sa.Column("event_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("event_payload_json", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.ForeignKeyConstraint(["intent_id"], ["canonical_intents.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["actor_user_id"], ["iam_users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_canonical_intent_events_tenant_id", "canonical_intent_events", ["tenant_id"])
    op.create_index("ix_canonical_intent_events_intent_id", "canonical_intent_events", ["intent_id"])

    _add_linkage_columns("accounting_jv_aggregates")
    _add_linkage_columns("accounting_jv_lines")
    _add_linkage_columns("accounting_jv_state_events")
    _add_linkage_columns("accounting_jv_approvals")
    _add_linkage_columns("gl_entries")

    op.execute(append_only_function_sql())
    op.execute(drop_trigger_sql("canonical_intent_events"))
    op.execute(create_trigger_sql("canonical_intent_events"))


def downgrade() -> None:
    op.execute(drop_trigger_sql("canonical_intent_events"))

    _drop_linkage_columns("gl_entries")
    _drop_linkage_columns("accounting_jv_approvals")
    _drop_linkage_columns("accounting_jv_state_events")
    _drop_linkage_columns("accounting_jv_lines")
    _drop_linkage_columns("accounting_jv_aggregates")

    op.drop_index("ix_canonical_intent_events_intent_id", table_name="canonical_intent_events")
    op.drop_index("ix_canonical_intent_events_tenant_id", table_name="canonical_intent_events")
    op.drop_table("canonical_intent_events")

    op.drop_index("ix_canonical_jobs_lookup", table_name="canonical_jobs")
    op.drop_index("ix_canonical_jobs_intent_id", table_name="canonical_jobs")
    op.drop_table("canonical_jobs")

    op.drop_index("ix_canonical_intents_lookup", table_name="canonical_intents")
    op.drop_index("ix_canonical_intents_job_id", table_name="canonical_intents")
    op.drop_index("ix_canonical_intents_target_id", table_name="canonical_intents")
    op.drop_index("ix_canonical_intents_entity_id", table_name="canonical_intents")
    op.drop_index("ix_canonical_intents_org_id", table_name="canonical_intents")
    op.drop_index("ix_canonical_intents_tenant_id", table_name="canonical_intents")
    op.drop_table("canonical_intents")


def _add_linkage_columns(table_name: str) -> None:
    op.add_column(table_name, sa.Column("created_by_intent_id", UUID(as_uuid=True), nullable=True))
    op.add_column(table_name, sa.Column("recorded_by_job_id", UUID(as_uuid=True), nullable=True))
    op.create_index(f"ix_{table_name}_created_by_intent_id", table_name, ["created_by_intent_id"])
    op.create_index(f"ix_{table_name}_recorded_by_job_id", table_name, ["recorded_by_job_id"])
    op.create_foreign_key(
        f"fk_{table_name}_created_by_intent_id",
        table_name,
        "canonical_intents",
        ["created_by_intent_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_foreign_key(
        f"fk_{table_name}_recorded_by_job_id",
        table_name,
        "canonical_jobs",
        ["recorded_by_job_id"],
        ["id"],
        ondelete="SET NULL",
    )


def _drop_linkage_columns(table_name: str) -> None:
    op.drop_constraint(f"fk_{table_name}_recorded_by_job_id", table_name, type_="foreignkey")
    op.drop_constraint(f"fk_{table_name}_created_by_intent_id", table_name, type_="foreignkey")
    op.drop_index(f"ix_{table_name}_recorded_by_job_id", table_name=table_name)
    op.drop_index(f"ix_{table_name}_created_by_intent_id", table_name=table_name)
    op.drop_column(table_name, "recorded_by_job_id")
    op.drop_column(table_name, "created_by_intent_id")
