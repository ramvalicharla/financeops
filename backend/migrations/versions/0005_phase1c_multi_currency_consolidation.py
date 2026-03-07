"""Phase 1C Multi-Currency Consolidation Engine

Revision ID: 0005_phase1c_consol
Revises: 0004_phase1b_fx
Create Date: 2026-03-07 00:00:00.000000
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

revision: str = "0005_phase1c_consol"
down_revision: str | None = "0004_phase1b_fx"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "normalized_financial_snapshots",
        sa.Column("snapshot_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("chain_hash", sa.String(64), nullable=False),
        sa.Column("previous_hash", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("entity_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("period_year", sa.Integer(), nullable=False),
        sa.Column("period_month", sa.Integer(), nullable=False),
        sa.Column("snapshot_type", sa.String(length=64), nullable=False),
        sa.Column("entity_currency", sa.String(length=3), nullable=False),
        sa.Column("produced_by_module", sa.String(length=64), nullable=False),
        sa.Column("source_artifact_reference", sa.String(length=255), nullable=False),
        sa.Column("supersedes_snapshot_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("correlation_id", sa.String(length=64), nullable=True),
        sa.ForeignKeyConstraint(
            ["supersedes_snapshot_id"],
            ["normalized_financial_snapshots.snapshot_id"],
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("snapshot_id"),
    )
    op.create_index(
        "idx_norm_snapshots_tenant_period",
        "normalized_financial_snapshots",
        ["tenant_id", "period_year", "period_month"],
    )
    op.create_index(
        "idx_norm_snapshots_entity",
        "normalized_financial_snapshots",
        ["tenant_id", "entity_id"],
    )
    op.create_index(
        "idx_norm_snapshots_type",
        "normalized_financial_snapshots",
        ["tenant_id", "snapshot_type"],
    )

    op.create_table(
        "normalized_financial_snapshot_lines",
        sa.Column("snapshot_line_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("chain_hash", sa.String(64), nullable=False),
        sa.Column("previous_hash", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("snapshot_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("account_code", sa.String(length=64), nullable=False),
        sa.Column("local_amount", sa.Numeric(20, 6), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("ic_reference", sa.String(length=255), nullable=True),
        sa.Column("counterparty_entity", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("transaction_date", sa.Date(), nullable=True),
        sa.Column("ic_account_class", sa.String(length=64), nullable=True),
        sa.Column("correlation_id", sa.String(length=64), nullable=True),
        sa.ForeignKeyConstraint(
            ["snapshot_id"],
            ["normalized_financial_snapshots.snapshot_id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("snapshot_line_id"),
    )
    op.create_index(
        "idx_norm_snapshot_lines_tenant_snapshot",
        "normalized_financial_snapshot_lines",
        ["tenant_id", "snapshot_id"],
    )
    op.create_index(
        "idx_norm_snapshot_lines_account",
        "normalized_financial_snapshot_lines",
        ["tenant_id", "snapshot_id", "account_code"],
    )

    op.create_table(
        "consolidation_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("chain_hash", sa.String(64), nullable=False),
        sa.Column("previous_hash", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("period_year", sa.Integer(), nullable=False),
        sa.Column("period_month", sa.Integer(), nullable=False),
        sa.Column("parent_currency", sa.String(length=3), nullable=False),
        sa.Column("initiated_by", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("request_signature", sa.String(length=64), nullable=False),
        sa.Column("configuration_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("workflow_id", sa.String(length=128), nullable=False),
        sa.Column("correlation_id", sa.String(length=64), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "request_signature", name="uq_consol_runs_tenant_signature"),
    )
    op.create_index(
        "idx_consol_runs_tenant_period",
        "consolidation_runs",
        ["tenant_id", "period_year", "period_month"],
    )
    op.create_index(
        "idx_consol_runs_tenant_created",
        "consolidation_runs",
        ["tenant_id", "created_at"],
    )

    op.create_table(
        "consolidation_run_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("chain_hash", sa.String(64), nullable=False),
        sa.Column("previous_hash", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("run_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("event_seq", sa.Integer(), nullable=False),
        sa.Column("event_type", sa.String(length=64), nullable=False),
        sa.Column("event_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("idempotency_key", sa.String(length=128), nullable=False),
        sa.Column("metadata_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("correlation_id", sa.String(length=64), nullable=True),
        sa.ForeignKeyConstraint(["run_id"], ["consolidation_runs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("run_id", "event_seq", name="uq_consol_run_events_seq"),
        sa.UniqueConstraint(
            "run_id",
            "event_type",
            "idempotency_key",
            name="uq_consol_run_events_idempotent",
        ),
    )
    op.create_index(
        "idx_consol_run_events_tenant_run",
        "consolidation_run_events",
        ["tenant_id", "run_id", "event_seq"],
    )

    op.create_table(
        "consolidation_entities",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("chain_hash", sa.String(64), nullable=False),
        sa.Column("previous_hash", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("run_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("entity_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("entity_currency", sa.String(length=3), nullable=False),
        sa.Column("source_snapshot_reference", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("expected_rate", sa.Numeric(20, 6), nullable=True),
        sa.Column("correlation_id", sa.String(length=64), nullable=True),
        sa.ForeignKeyConstraint(["run_id"], ["consolidation_runs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["source_snapshot_reference"],
            ["normalized_financial_snapshots.snapshot_id"],
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "run_id", "entity_id", name="uq_consol_entities_run_entity"),
    )
    op.create_index(
        "idx_consol_entities_tenant_run",
        "consolidation_entities",
        ["tenant_id", "run_id"],
    )

    op.create_table(
        "consolidation_line_items",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("chain_hash", sa.String(64), nullable=False),
        sa.Column("previous_hash", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("run_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("entity_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("snapshot_line_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("account_code", sa.String(length=64), nullable=False),
        sa.Column("local_currency", sa.String(length=3), nullable=False),
        sa.Column("local_amount", sa.Numeric(20, 6), nullable=False),
        sa.Column("fx_rate_used", sa.Numeric(20, 6), nullable=False),
        sa.Column("expected_rate", sa.Numeric(20, 6), nullable=False),
        sa.Column("parent_amount", sa.Numeric(20, 6), nullable=False),
        sa.Column("fx_delta_component", sa.Numeric(20, 6), nullable=False),
        sa.Column("ic_reference", sa.String(length=255), nullable=True),
        sa.Column("ic_counterparty_entity", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("transaction_date", sa.Date(), nullable=True),
        sa.Column("correlation_id", sa.String(length=64), nullable=True),
        sa.ForeignKeyConstraint(["run_id"], ["consolidation_runs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["snapshot_line_id"],
            ["normalized_financial_snapshot_lines.snapshot_line_id"],
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("run_id", "snapshot_line_id", name="uq_consol_lines_snapshot"),
    )
    op.create_index(
        "idx_consol_lines_tenant_run",
        "consolidation_line_items",
        ["tenant_id", "run_id"],
    )
    op.create_index(
        "idx_consol_lines_account",
        "consolidation_line_items",
        ["tenant_id", "run_id", "account_code"],
    )

    op.create_table(
        "intercompany_pairs",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("chain_hash", sa.String(64), nullable=False),
        sa.Column("previous_hash", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("run_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("match_key_hash", sa.String(length=64), nullable=False),
        sa.Column("entity_from", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("entity_to", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("account_code", sa.String(length=64), nullable=False),
        sa.Column("ic_reference", sa.String(length=255), nullable=True),
        sa.Column("amount_local_from", sa.Numeric(20, 6), nullable=False),
        sa.Column("amount_local_to", sa.Numeric(20, 6), nullable=False),
        sa.Column("amount_parent_from", sa.Numeric(20, 6), nullable=False),
        sa.Column("amount_parent_to", sa.Numeric(20, 6), nullable=False),
        sa.Column("expected_difference", sa.Numeric(20, 6), nullable=False),
        sa.Column("actual_difference", sa.Numeric(20, 6), nullable=False),
        sa.Column("fx_explained", sa.Numeric(20, 6), nullable=False),
        sa.Column("unexplained_difference", sa.Numeric(20, 6), nullable=False),
        sa.Column("classification", sa.String(length=64), nullable=False),
        sa.Column("correlation_id", sa.String(length=64), nullable=True),
        sa.ForeignKeyConstraint(["run_id"], ["consolidation_runs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("run_id", "match_key_hash", name="uq_intercompany_pairs_match_key"),
    )
    op.create_index(
        "idx_ic_pairs_tenant_run",
        "intercompany_pairs",
        ["tenant_id", "run_id"],
    )
    op.create_index(
        "idx_ic_pairs_classification",
        "intercompany_pairs",
        ["tenant_id", "run_id", "classification"],
    )

    op.create_table(
        "consolidation_eliminations",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("chain_hash", sa.String(64), nullable=False),
        sa.Column("previous_hash", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("run_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("intercompany_pair_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("entity_from", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("entity_to", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("account_code", sa.String(length=64), nullable=False),
        sa.Column("classification_at_time", sa.String(length=64), nullable=False),
        sa.Column("elimination_status", sa.String(length=32), nullable=False),
        sa.Column("eliminated_amount_parent", sa.Numeric(20, 6), nullable=False),
        sa.Column("fx_component_impact_parent", sa.Numeric(20, 6), nullable=False),
        sa.Column("residual_difference_parent", sa.Numeric(20, 6), nullable=False),
        sa.Column("rule_code", sa.String(length=64), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("correlation_id", sa.String(length=64), nullable=True),
        sa.ForeignKeyConstraint(["intercompany_pair_id"], ["intercompany_pairs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["run_id"], ["consolidation_runs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "idx_consol_elims_tenant_run",
        "consolidation_eliminations",
        ["tenant_id", "run_id"],
    )
    op.create_index(
        "idx_consol_elims_status",
        "consolidation_eliminations",
        ["tenant_id", "run_id", "elimination_status"],
    )

    op.create_table(
        "consolidation_results",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("chain_hash", sa.String(64), nullable=False),
        sa.Column("previous_hash", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("run_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("consolidated_account_code", sa.String(length=64), nullable=False),
        sa.Column("consolidated_amount_parent", sa.Numeric(20, 6), nullable=False),
        sa.Column("fx_impact_total", sa.Numeric(20, 6), nullable=False),
        sa.Column("correlation_id", sa.String(length=64), nullable=True),
        sa.ForeignKeyConstraint(["run_id"], ["consolidation_runs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("run_id", "consolidated_account_code", name="uq_consol_results_account"),
    )
    op.create_index(
        "idx_consol_results_tenant_run",
        "consolidation_results",
        ["tenant_id", "run_id"],
    )

    consolidation_tables = [
        "normalized_financial_snapshots",
        "normalized_financial_snapshot_lines",
        "consolidation_runs",
        "consolidation_run_events",
        "consolidation_entities",
        "consolidation_line_items",
        "intercompany_pairs",
        "consolidation_eliminations",
        "consolidation_results",
    ]
    for table_name in consolidation_tables:
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
    for table_name in consolidation_tables:
        op.execute(drop_trigger_sql(table_name))
        op.execute(create_trigger_sql(table_name))


def downgrade() -> None:
    consolidation_tables = [
        "consolidation_results",
        "consolidation_eliminations",
        "intercompany_pairs",
        "consolidation_line_items",
        "consolidation_entities",
        "consolidation_run_events",
        "consolidation_runs",
        "normalized_financial_snapshot_lines",
        "normalized_financial_snapshots",
    ]
    for table_name in consolidation_tables:
        op.execute(drop_trigger_sql(table_name))
        op.drop_table(table_name)
