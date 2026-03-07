"""Phase 1F.3.1 Payroll-GL reconciliation domain module

Revision ID: 0015_phase1f3_1_pg_gl_recon
Revises: 0014_phase1f3_pglnorm
Create Date: 2026-03-08 18:00:00.000000
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

revision: str = "0015_phase1f3_1_pg_gl_recon"
down_revision: str | None = "0014_phase1f3_pglnorm"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "payroll_gl_reconciliation_mappings",
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
        sa.Column("mapping_code", sa.String(length=64), nullable=False),
        sa.Column("mapping_name", sa.String(length=255), nullable=False),
        sa.Column("payroll_metric_code", sa.String(length=128), nullable=False),
        sa.Column(
            "gl_account_selector_json",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "cost_center_rule_json",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "department_rule_json",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "entity_rule_json",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("effective_from", sa.Date(), nullable=False),
        sa.Column("supersedes_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="candidate"),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["supersedes_id"],
            ["payroll_gl_reconciliation_mappings.id"],
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint(
            "status IN ('candidate','active','superseded','rejected')",
            name="ck_payroll_gl_recon_mappings_status",
        ),
    )
    op.create_index(
        "idx_payroll_gl_recon_mappings_lookup",
        "payroll_gl_reconciliation_mappings",
        ["tenant_id", "organisation_id", "mapping_code", "created_at"],
    )
    op.create_index(
        "uq_payroll_gl_recon_mappings_one_active",
        "payroll_gl_reconciliation_mappings",
        ["tenant_id", "organisation_id", "mapping_code"],
        unique=True,
        postgresql_where=sa.text("status = 'active'"),
    )

    op.execute(
        """
        CREATE OR REPLACE FUNCTION payroll_gl_recon_mappings_validate_supersession()
        RETURNS trigger AS $$
        DECLARE
            parent_mapping_code text;
            parent_tenant_id uuid;
            parent_org_id uuid;
        BEGIN
            IF NEW.supersedes_id IS NOT NULL THEN
                IF NEW.supersedes_id = NEW.id THEN
                    RAISE EXCEPTION 'self-supersession is not allowed';
                END IF;

                SELECT mapping_code, tenant_id, organisation_id
                INTO parent_mapping_code, parent_tenant_id, parent_org_id
                FROM payroll_gl_reconciliation_mappings
                WHERE id = NEW.supersedes_id;

                IF parent_mapping_code IS NULL THEN
                    RAISE EXCEPTION 'supersedes_id must reference existing mapping version';
                END IF;

                IF parent_mapping_code <> NEW.mapping_code
                   OR parent_tenant_id <> NEW.tenant_id
                   OR parent_org_id <> NEW.organisation_id THEN
                    RAISE EXCEPTION 'supersession across mapping codes is not allowed';
                END IF;

                IF EXISTS (
                    SELECT 1
                    FROM payroll_gl_reconciliation_mappings
                    WHERE supersedes_id = NEW.supersedes_id
                ) THEN
                    RAISE EXCEPTION 'supersession branching is not allowed';
                END IF;

                IF EXISTS (
                    WITH RECURSIVE chain(id, supersedes_id) AS (
                        SELECT id, supersedes_id
                        FROM payroll_gl_reconciliation_mappings
                        WHERE id = NEW.supersedes_id
                        UNION ALL
                        SELECT v.id, v.supersedes_id
                        FROM payroll_gl_reconciliation_mappings v
                        INNER JOIN chain c ON v.id = c.supersedes_id
                        WHERE c.supersedes_id IS NOT NULL
                    )
                    SELECT 1 FROM chain WHERE id = NEW.id
                ) THEN
                    RAISE EXCEPTION 'supersession cycle detected';
                END IF;
            END IF;

            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_payroll_gl_recon_mappings_validate_supersession
        BEFORE INSERT ON payroll_gl_reconciliation_mappings
        FOR EACH ROW
        EXECUTE FUNCTION payroll_gl_recon_mappings_validate_supersession();
        """
    )

    op.create_table(
        "payroll_gl_reconciliation_rules",
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
        sa.Column("rule_code", sa.String(length=64), nullable=False),
        sa.Column("rule_name", sa.String(length=255), nullable=False),
        sa.Column("rule_type", sa.String(length=64), nullable=False),
        sa.Column(
            "tolerance_json",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "materiality_json",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "timing_window_json",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "classification_behavior_json",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("effective_from", sa.Date(), nullable=False),
        sa.Column("supersedes_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="candidate"),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["supersedes_id"],
            ["payroll_gl_reconciliation_rules.id"],
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint(
            "rule_type IN ("
            "'aggregate_tie_rule','component_tie_rule','timing_rule',"
            "'contribution_rule','payable_rule','cost_center_rule'"
            ")",
            name="ck_payroll_gl_recon_rules_type",
        ),
        sa.CheckConstraint(
            "status IN ('candidate','active','superseded','rejected')",
            name="ck_payroll_gl_recon_rules_status",
        ),
    )
    op.create_index(
        "idx_payroll_gl_recon_rules_lookup",
        "payroll_gl_reconciliation_rules",
        ["tenant_id", "organisation_id", "rule_code", "created_at"],
    )
    op.create_index(
        "uq_payroll_gl_recon_rules_one_active",
        "payroll_gl_reconciliation_rules",
        ["tenant_id", "organisation_id", "rule_code"],
        unique=True,
        postgresql_where=sa.text("status = 'active'"),
    )

    op.execute(
        """
        CREATE OR REPLACE FUNCTION payroll_gl_recon_rules_validate_supersession()
        RETURNS trigger AS $$
        DECLARE
            parent_rule_code text;
            parent_tenant_id uuid;
            parent_org_id uuid;
        BEGIN
            IF NEW.supersedes_id IS NOT NULL THEN
                IF NEW.supersedes_id = NEW.id THEN
                    RAISE EXCEPTION 'self-supersession is not allowed';
                END IF;

                SELECT rule_code, tenant_id, organisation_id
                INTO parent_rule_code, parent_tenant_id, parent_org_id
                FROM payroll_gl_reconciliation_rules
                WHERE id = NEW.supersedes_id;

                IF parent_rule_code IS NULL THEN
                    RAISE EXCEPTION 'supersedes_id must reference existing rule version';
                END IF;

                IF parent_rule_code <> NEW.rule_code
                   OR parent_tenant_id <> NEW.tenant_id
                   OR parent_org_id <> NEW.organisation_id THEN
                    RAISE EXCEPTION 'supersession across rule codes is not allowed';
                END IF;

                IF EXISTS (
                    SELECT 1
                    FROM payroll_gl_reconciliation_rules
                    WHERE supersedes_id = NEW.supersedes_id
                ) THEN
                    RAISE EXCEPTION 'supersession branching is not allowed';
                END IF;

                IF EXISTS (
                    WITH RECURSIVE chain(id, supersedes_id) AS (
                        SELECT id, supersedes_id
                        FROM payroll_gl_reconciliation_rules
                        WHERE id = NEW.supersedes_id
                        UNION ALL
                        SELECT v.id, v.supersedes_id
                        FROM payroll_gl_reconciliation_rules v
                        INNER JOIN chain c ON v.id = c.supersedes_id
                        WHERE c.supersedes_id IS NOT NULL
                    )
                    SELECT 1 FROM chain WHERE id = NEW.id
                ) THEN
                    RAISE EXCEPTION 'supersession cycle detected';
                END IF;
            END IF;

            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_payroll_gl_recon_rules_validate_supersession
        BEFORE INSERT ON payroll_gl_reconciliation_rules
        FOR EACH ROW
        EXECUTE FUNCTION payroll_gl_recon_rules_validate_supersession();
        """
    )

    op.create_table(
        "payroll_gl_reconciliation_runs",
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
        sa.Column("reconciliation_session_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("payroll_run_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("gl_run_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("mapping_version_token", sa.String(length=64), nullable=False),
        sa.Column("rule_version_token", sa.String(length=64), nullable=False),
        sa.Column("reporting_period", sa.Date(), nullable=False),
        sa.Column("run_token", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="created"),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["reconciliation_session_id"],
            ["reconciliation_sessions.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["payroll_run_id"],
            ["normalization_runs.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["gl_run_id"],
            ["normalization_runs.id"],
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "tenant_id",
            "run_token",
            name="uq_payroll_gl_recon_runs_tenant_token",
        ),
        sa.CheckConstraint(
            "status IN ('created','running','completed','failed')",
            name="ck_payroll_gl_recon_runs_status",
        ),
    )
    op.create_index(
        "idx_payroll_gl_recon_runs_lookup",
        "payroll_gl_reconciliation_runs",
        ["tenant_id", "organisation_id", "reporting_period", "created_at"],
    )
    op.create_index(
        "idx_payroll_gl_recon_runs_session",
        "payroll_gl_reconciliation_runs",
        ["tenant_id", "reconciliation_session_id"],
    )

    op.create_table(
        "payroll_gl_reconciliation_run_scopes",
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
        sa.Column("payroll_gl_reconciliation_run_id", postgresql.UUID(as_uuid=True), nullable=False),
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
            ["payroll_gl_reconciliation_run_id"],
            ["payroll_gl_reconciliation_runs.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "payroll_gl_reconciliation_run_id",
            "scope_code",
            name="uq_payroll_gl_recon_run_scopes_code",
        ),
    )
    op.create_index(
        "idx_payroll_gl_recon_run_scopes_run",
        "payroll_gl_reconciliation_run_scopes",
        ["tenant_id", "payroll_gl_reconciliation_run_id"],
    )

    rls_tables = [
        "payroll_gl_reconciliation_mappings",
        "payroll_gl_reconciliation_rules",
        "payroll_gl_reconciliation_runs",
        "payroll_gl_reconciliation_run_scopes",
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
        "payroll_gl_reconciliation_mappings",
        "payroll_gl_reconciliation_rules",
        "payroll_gl_reconciliation_runs",
        "payroll_gl_reconciliation_run_scopes",
    ]
    for table_name in append_only_tables:
        op.execute(drop_trigger_sql(table_name))
        op.execute(create_trigger_sql(table_name))


def downgrade() -> None:
    op.execute(
        "DROP TRIGGER IF EXISTS trg_payroll_gl_recon_mappings_validate_supersession "
        "ON payroll_gl_reconciliation_mappings"
    )
    op.execute(
        "DROP FUNCTION IF EXISTS payroll_gl_recon_mappings_validate_supersession()"
    )
    op.execute(
        "DROP TRIGGER IF EXISTS trg_payroll_gl_recon_rules_validate_supersession "
        "ON payroll_gl_reconciliation_rules"
    )
    op.execute(
        "DROP FUNCTION IF EXISTS payroll_gl_recon_rules_validate_supersession()"
    )

    drop_order = [
        "payroll_gl_reconciliation_run_scopes",
        "payroll_gl_reconciliation_runs",
        "payroll_gl_reconciliation_rules",
        "payroll_gl_reconciliation_mappings",
    ]
    for table_name in drop_order:
        op.execute(drop_trigger_sql(table_name))
        op.drop_table(table_name)
