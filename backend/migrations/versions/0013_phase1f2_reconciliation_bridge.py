"""Phase 1F.2 Reconciliation Bridge deterministic control layer

Revision ID: 0013_phase1f2_recon_bridge
Revises: 0012_phase1f1_mis_manager
Create Date: 2026-03-08 00:10:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

from financeops.db.append_only import (
    append_only_function_sql,
    create_trigger_sql,
    drop_trigger_sql,
)

revision: str = "0013_phase1f2_recon_bridge"
down_revision: str | None = "0012_phase1f1_mis_manager"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "reconciliation_sessions",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("chain_hash", sa.String(length=64), nullable=False),
        sa.Column("previous_hash", sa.String(length=64), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("organisation_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("reconciliation_type", sa.String(length=64), nullable=False),
        sa.Column("source_a_type", sa.String(length=64), nullable=False),
        sa.Column("source_a_ref", sa.Text(), nullable=False),
        sa.Column("source_b_type", sa.String(length=64), nullable=False),
        sa.Column("source_b_ref", sa.Text(), nullable=False),
        sa.Column("period_start", sa.Date(), nullable=False),
        sa.Column("period_end", sa.Date(), nullable=False),
        sa.Column("matching_rule_version", sa.String(length=64), nullable=False),
        sa.Column("tolerance_rule_version", sa.String(length=64), nullable=False),
        sa.Column("session_token", sa.String(length=64), nullable=False),
        sa.Column(
            "materiality_config_json",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="created"),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("session_token", name="uq_reconciliation_sessions_token"),
        sa.CheckConstraint(
            "status IN ('created','running','completed','failed')",
            name="ck_reconciliation_sessions_status",
        ),
    )
    op.create_index(
        "idx_recon_session_tenant",
        "reconciliation_sessions",
        ["tenant_id", "created_at"],
    )
    op.create_index(
        "idx_recon_session_token",
        "reconciliation_sessions",
        ["session_token"],
        unique=True,
    )

    op.create_table(
        "reconciliation_scopes",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("chain_hash", sa.String(length=64), nullable=False),
        sa.Column("previous_hash", sa.String(length=64), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("session_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("scope_code", sa.String(length=64), nullable=False),
        sa.Column("scope_label", sa.String(length=255), nullable=False),
        sa.Column(
            "scope_json",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["session_id"], ["reconciliation_sessions.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "session_id",
            "scope_code",
            name="uq_reconciliation_scopes_session_scope_code",
        ),
    )
    op.create_index(
        "idx_reconciliation_scopes_session",
        "reconciliation_scopes",
        ["tenant_id", "session_id"],
    )

    op.create_table(
        "reconciliation_lines",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("chain_hash", sa.String(length=64), nullable=False),
        sa.Column("previous_hash", sa.String(length=64), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("session_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("scope_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("line_key", sa.String(length=128), nullable=False),
        sa.Column(
            "comparison_dimension_json",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("source_a_value", sa.Numeric(20, 6), nullable=False),
        sa.Column("source_b_value", sa.Numeric(20, 6), nullable=False),
        sa.Column("variance_value", sa.Numeric(20, 6), nullable=False),
        sa.Column("variance_abs", sa.Numeric(20, 6), nullable=False),
        sa.Column("variance_pct", sa.Numeric(20, 6), nullable=False),
        sa.Column("currency_code", sa.String(length=3), nullable=False),
        sa.Column("reconciliation_status", sa.String(length=32), nullable=False),
        sa.Column("difference_type", sa.String(length=64), nullable=False),
        sa.Column(
            "materiality_flag",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column("explanation_hint", sa.Text(), nullable=True),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["session_id"], ["reconciliation_sessions.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["scope_id"], ["reconciliation_scopes.id"], ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "session_id", "line_key", name="uq_reconciliation_lines_session_line_key"
        ),
        sa.CheckConstraint(
            "reconciliation_status IN ('matched','exception','review_required')",
            name="ck_reconciliation_lines_status",
        ),
        sa.CheckConstraint(
            "difference_type IN "
            "('missing_in_a','missing_in_b','value_mismatch','mapping_gap',"
            "'timing_difference','classification_difference','fx_difference',"
            "'aggregation_difference','none')",
            name="ck_reconciliation_lines_difference_type",
        ),
    )
    op.create_index(
        "idx_recon_lines_session", "reconciliation_lines", ["tenant_id", "session_id"]
    )
    op.create_index(
        "idx_recon_lines_status",
        "reconciliation_lines",
        ["tenant_id", "session_id", "reconciliation_status"],
    )
    op.create_index(
        "idx_recon_lines_difference_type",
        "reconciliation_lines",
        ["tenant_id", "session_id", "difference_type"],
    )
    op.create_index(
        "idx_recon_lines_line_key",
        "reconciliation_lines",
        ["tenant_id", "session_id", "line_key"],
    )

    op.create_table(
        "reconciliation_exceptions",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("chain_hash", sa.String(length=64), nullable=False),
        sa.Column("previous_hash", sa.String(length=64), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("session_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("line_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("exception_code", sa.String(length=64), nullable=False),
        sa.Column("severity", sa.String(length=16), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("owner_role", sa.String(length=64), nullable=True),
        sa.Column(
            "resolution_status", sa.String(length=32), nullable=False, server_default="open"
        ),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["session_id"], ["reconciliation_sessions.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["line_id"], ["reconciliation_lines.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint(
            "severity IN ('info','warning','error')",
            name="ck_reconciliation_exceptions_severity",
        ),
        sa.CheckConstraint(
            "resolution_status IN ('open','resolved','reopened','accepted')",
            name="ck_reconciliation_exceptions_resolution_status",
        ),
    )
    op.create_index(
        "idx_recon_exception_by_session",
        "reconciliation_exceptions",
        ["tenant_id", "session_id", "created_at"],
    )

    op.create_table(
        "reconciliation_resolution_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("chain_hash", sa.String(length=64), nullable=False),
        sa.Column("previous_hash", sa.String(length=64), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("session_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("line_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("exception_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("event_type", sa.String(length=64), nullable=False),
        sa.Column(
            "event_payload_json",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("actor_user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["session_id"], ["reconciliation_sessions.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["line_id"], ["reconciliation_lines.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["exception_id"], ["reconciliation_exceptions.id"], ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint(
            "event_type IN ("
            "'exception_opened','explanation_added','evidence_linked','assigned',"
            "'accepted_timing_difference','accepted_mapping_gap','escalated',"
            "'resolved','reopened'"
            ")",
            name="ck_reconciliation_resolution_events_event_type",
        ),
    )
    op.create_index(
        "idx_recon_resolution_event_by_line",
        "reconciliation_resolution_events",
        ["tenant_id", "line_id", "created_at"],
    )
    op.create_index(
        "idx_recon_resolution_event_by_session",
        "reconciliation_resolution_events",
        ["tenant_id", "session_id", "created_at"],
    )

    op.create_table(
        "reconciliation_evidence_links",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("chain_hash", sa.String(length=64), nullable=False),
        sa.Column("previous_hash", sa.String(length=64), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("session_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("line_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("evidence_type", sa.String(length=64), nullable=False),
        sa.Column("evidence_ref", sa.Text(), nullable=False),
        sa.Column("evidence_label", sa.String(length=255), nullable=False),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["session_id"], ["reconciliation_sessions.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["line_id"], ["reconciliation_lines.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint(
            "evidence_type IN ("
            "'mis_snapshot_line','tb_line','gl_entry','schedule_row',"
            "'far_depreciation_row','lease_liability_row','uploaded_artifact'"
            ")",
            name="ck_reconciliation_evidence_links_evidence_type",
        ),
    )
    op.create_index(
        "idx_recon_evidence_by_line",
        "reconciliation_evidence_links",
        ["tenant_id", "line_id", "created_at"],
    )
    op.create_index(
        "idx_recon_evidence_by_session",
        "reconciliation_evidence_links",
        ["tenant_id", "session_id", "created_at"],
    )

    rls_tables = [
        "reconciliation_sessions",
        "reconciliation_scopes",
        "reconciliation_lines",
        "reconciliation_exceptions",
        "reconciliation_resolution_events",
        "reconciliation_evidence_links",
    ]
    for table_name in rls_tables:
        op.execute(f"ALTER TABLE {table_name} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table_name} FORCE ROW LEVEL SECURITY")
        op.execute(
            f"""
            CREATE POLICY {table_name}_tenant_isolation
            ON {table_name}
            USING (tenant_id = current_setting('app.current_tenant_id', true)::uuid)
            """
        )

    op.execute(append_only_function_sql())
    append_only_tables = [
        "reconciliation_sessions",
        "reconciliation_scopes",
        "reconciliation_lines",
        "reconciliation_exceptions",
        "reconciliation_resolution_events",
        "reconciliation_evidence_links",
    ]
    for table_name in append_only_tables:
        op.execute(drop_trigger_sql(table_name))
        op.execute(create_trigger_sql(table_name))


def downgrade() -> None:
    drop_order = [
        "reconciliation_evidence_links",
        "reconciliation_resolution_events",
        "reconciliation_exceptions",
        "reconciliation_lines",
        "reconciliation_scopes",
        "reconciliation_sessions",
    ]
    for table_name in drop_order:
        op.execute(drop_trigger_sql(table_name))
        op.drop_table(table_name)
