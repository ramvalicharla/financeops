"""Phase 1F.3 Payroll / GL normalization contract layer

Revision ID: 0014_phase1f3_pglnorm
Revises: 0013_phase1f2_recon_bridge
Create Date: 2026-03-08 02:00:00.000000
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

revision: str = "0014_phase1f3_pglnorm"
down_revision: str | None = "0013_phase1f2_recon_bridge"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "normalization_sources",
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
        sa.Column("source_family", sa.String(length=64), nullable=False),
        sa.Column("source_code", sa.String(length=128), nullable=False),
        sa.Column("source_name", sa.String(length=255), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="active"),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "tenant_id",
            "source_code",
            name="uq_normalization_sources_tenant_code",
        ),
        sa.CheckConstraint(
            "status IN ('active','inactive','archived')",
            name="ck_normalization_sources_status",
        ),
    )
    op.create_index(
        "idx_normalization_sources_tenant",
        "normalization_sources",
        ["tenant_id", "created_at"],
    )
    op.create_index(
        "idx_normalization_sources_family_code",
        "normalization_sources",
        ["tenant_id", "source_family", "source_code"],
    )

    op.create_table(
        "normalization_source_versions",
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
        sa.Column("source_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("version_no", sa.Integer(), nullable=False),
        sa.Column("version_token", sa.String(length=64), nullable=False),
        sa.Column("structure_hash", sa.String(length=64), nullable=False),
        sa.Column("header_hash", sa.String(length=64), nullable=False),
        sa.Column("row_signature_hash", sa.String(length=64), nullable=False),
        sa.Column(
            "source_detection_summary_json",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("supersedes_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="candidate"),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["source_id"], ["normalization_sources.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["supersedes_id"], ["normalization_source_versions.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "source_id",
            "version_no",
            name="uq_normalization_source_versions_source_no",
        ),
        sa.UniqueConstraint(
            "source_id",
            "version_token",
            name="uq_normalization_source_versions_source_token",
        ),
        sa.CheckConstraint(
            "status IN ('candidate','active','superseded','rejected')",
            name="ck_normalization_source_versions_status",
        ),
    )
    op.create_index(
        "idx_normalization_source_versions_source",
        "normalization_source_versions",
        ["tenant_id", "source_id", "created_at"],
    )
    op.create_index(
        "uq_normalization_source_versions_one_active",
        "normalization_source_versions",
        ["source_id"],
        unique=True,
        postgresql_where=sa.text("status = 'active'"),
    )

    op.execute(
        """
        CREATE OR REPLACE FUNCTION normalization_source_versions_validate_supersession()
        RETURNS trigger AS $$
        DECLARE
            parent_source_id uuid;
        BEGIN
            IF NEW.supersedes_id IS NOT NULL THEN
                IF NEW.supersedes_id = NEW.id THEN
                    RAISE EXCEPTION 'self-supersession is not allowed';
                END IF;

                SELECT source_id INTO parent_source_id
                FROM normalization_source_versions
                WHERE id = NEW.supersedes_id;

                IF parent_source_id IS NULL THEN
                    RAISE EXCEPTION 'supersedes_id must reference existing source version';
                END IF;

                IF parent_source_id <> NEW.source_id THEN
                    RAISE EXCEPTION 'supersession across normalization sources is not allowed';
                END IF;

                IF EXISTS (
                    SELECT 1
                    FROM normalization_source_versions
                    WHERE supersedes_id = NEW.supersedes_id
                ) THEN
                    RAISE EXCEPTION 'supersession branching is not allowed';
                END IF;

                IF EXISTS (
                    WITH RECURSIVE chain(id, supersedes_id) AS (
                        SELECT id, supersedes_id
                        FROM normalization_source_versions
                        WHERE id = NEW.supersedes_id
                        UNION ALL
                        SELECT v.id, v.supersedes_id
                        FROM normalization_source_versions v
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
        CREATE TRIGGER trg_normalization_source_versions_validate_supersession
        BEFORE INSERT ON normalization_source_versions
        FOR EACH ROW
        EXECUTE FUNCTION normalization_source_versions_validate_supersession();
        """
    )

    op.create_table(
        "normalization_mappings",
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
        sa.Column("source_version_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("mapping_type", sa.String(length=32), nullable=False),
        sa.Column("source_field_name", sa.String(length=255), nullable=False),
        sa.Column("canonical_field_name", sa.String(length=128), nullable=False),
        sa.Column("transform_rule", sa.String(length=64), nullable=True),
        sa.Column(
            "default_value_json",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("required_flag", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("confidence_score", sa.Numeric(5, 4), nullable=False),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["source_version_id"],
            ["normalization_source_versions.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint(
            "mapping_type IN ('payroll_dimension','payroll_metric','gl_dimension','gl_metric')",
            name="ck_normalization_mappings_type",
        ),
        sa.CheckConstraint(
            "confidence_score >= 0 AND confidence_score <= 1",
            name="ck_normalization_mappings_confidence",
        ),
    )
    op.create_index(
        "idx_normalization_mappings_source_version",
        "normalization_mappings",
        ["tenant_id", "source_version_id", "mapping_type"],
    )
    op.create_index(
        "idx_normalization_mappings_field",
        "normalization_mappings",
        ["tenant_id", "source_version_id", "canonical_field_name"],
    )

    op.create_table(
        "normalization_runs",
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
        sa.Column("source_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("source_version_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("mapping_version_token", sa.String(length=64), nullable=False),
        sa.Column("run_type", sa.String(length=64), nullable=False),
        sa.Column("reporting_period", sa.Date(), nullable=False),
        sa.Column("source_artifact_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("source_file_hash", sa.String(length=64), nullable=False),
        sa.Column("run_token", sa.String(length=64), nullable=False),
        sa.Column("run_status", sa.String(length=32), nullable=False, server_default="pending"),
        sa.Column(
            "validation_summary_json",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["source_id"], ["normalization_sources.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["source_version_id"], ["normalization_source_versions.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "tenant_id",
            "run_token",
            name="uq_normalization_runs_tenant_token",
        ),
        sa.CheckConstraint(
            "run_type IN ('payroll_normalization','gl_normalization')",
            name="ck_normalization_runs_type",
        ),
        sa.CheckConstraint(
            "run_status IN ('pending','validated','finalized','failed')",
            name="ck_normalization_runs_status",
        ),
    )
    op.create_index(
        "idx_normalization_runs_source_period",
        "normalization_runs",
        ["tenant_id", "source_id", "reporting_period"],
    )
    op.create_index(
        "idx_normalization_runs_token",
        "normalization_runs",
        ["tenant_id", "run_token"],
        unique=True,
    )

    op.create_table(
        "payroll_normalized_lines",
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
        sa.Column("run_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("row_no", sa.Integer(), nullable=False),
        sa.Column("employee_code", sa.String(length=128), nullable=True),
        sa.Column("employee_name", sa.String(length=255), nullable=True),
        sa.Column("payroll_period", sa.Date(), nullable=False),
        sa.Column("legal_entity", sa.String(length=255), nullable=True),
        sa.Column("department", sa.String(length=255), nullable=True),
        sa.Column("cost_center", sa.String(length=255), nullable=True),
        sa.Column("business_unit", sa.String(length=255), nullable=True),
        sa.Column("location", sa.String(length=255), nullable=True),
        sa.Column("grade", sa.String(length=128), nullable=True),
        sa.Column("designation", sa.String(length=255), nullable=True),
        sa.Column("currency_code", sa.String(length=3), nullable=False),
        sa.Column("canonical_metric_code", sa.String(length=128), nullable=False),
        sa.Column("amount_value", sa.Numeric(20, 6), nullable=False),
        sa.Column("source_row_ref", sa.String(length=128), nullable=False),
        sa.Column("source_column_ref", sa.String(length=128), nullable=False),
        sa.Column("normalization_status", sa.String(length=16), nullable=False),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["run_id"], ["normalization_runs.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "run_id",
            "row_no",
            "employee_code",
            "canonical_metric_code",
            name="uq_payroll_normalized_lines_row_metric",
        ),
        sa.CheckConstraint(
            "normalization_status IN ('valid','warning','invalid')",
            name="ck_payroll_normalized_lines_status",
        ),
    )
    op.create_index(
        "idx_payroll_normalized_lines_run",
        "payroll_normalized_lines",
        ["tenant_id", "run_id", "row_no"],
    )
    op.create_index(
        "idx_payroll_normalized_lines_employee_period",
        "payroll_normalized_lines",
        ["tenant_id", "employee_code", "payroll_period"],
    )
    op.create_index(
        "idx_payroll_normalized_lines_metric",
        "payroll_normalized_lines",
        ["tenant_id", "canonical_metric_code", "payroll_period"],
    )

    op.create_table(
        "gl_normalized_lines",
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
        sa.Column("run_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("row_no", sa.Integer(), nullable=False),
        sa.Column("journal_id", sa.String(length=128), nullable=True),
        sa.Column("journal_line_no", sa.String(length=64), nullable=True),
        sa.Column("posting_date", sa.Date(), nullable=True),
        sa.Column("document_date", sa.Date(), nullable=True),
        sa.Column("posting_period", sa.String(length=16), nullable=False),
        sa.Column("legal_entity", sa.String(length=255), nullable=True),
        sa.Column("account_code", sa.String(length=128), nullable=True),
        sa.Column("account_name", sa.String(length=255), nullable=True),
        sa.Column("cost_center", sa.String(length=255), nullable=True),
        sa.Column("department", sa.String(length=255), nullable=True),
        sa.Column("business_unit", sa.String(length=255), nullable=True),
        sa.Column("project", sa.String(length=255), nullable=True),
        sa.Column("customer", sa.String(length=255), nullable=True),
        sa.Column("vendor", sa.String(length=255), nullable=True),
        sa.Column("source_module", sa.String(length=128), nullable=True),
        sa.Column("source_document_id", sa.String(length=255), nullable=True),
        sa.Column("currency_code", sa.String(length=3), nullable=False),
        sa.Column("debit_amount", sa.Numeric(20, 6), nullable=False),
        sa.Column("credit_amount", sa.Numeric(20, 6), nullable=False),
        sa.Column("signed_amount", sa.Numeric(20, 6), nullable=False),
        sa.Column("local_amount", sa.Numeric(20, 6), nullable=False),
        sa.Column("transaction_amount", sa.Numeric(20, 6), nullable=False),
        sa.Column("source_row_ref", sa.String(length=128), nullable=False),
        sa.Column("source_column_ref", sa.String(length=128), nullable=False),
        sa.Column("normalization_status", sa.String(length=16), nullable=False),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["run_id"], ["normalization_runs.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "run_id",
            "row_no",
            name="uq_gl_normalized_lines_run_row",
        ),
        sa.CheckConstraint(
            "normalization_status IN ('valid','warning','invalid')",
            name="ck_gl_normalized_lines_status",
        ),
    )
    op.create_index(
        "idx_gl_normalized_lines_run",
        "gl_normalized_lines",
        ["tenant_id", "run_id", "row_no"],
    )
    op.create_index(
        "idx_gl_normalized_lines_account_period",
        "gl_normalized_lines",
        ["tenant_id", "account_code", "posting_period"],
    )

    op.create_table(
        "normalization_exceptions",
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
        sa.Column("run_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("exception_code", sa.String(length=64), nullable=False),
        sa.Column("severity", sa.String(length=16), nullable=False),
        sa.Column("source_ref", sa.String(length=255), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column(
            "resolution_status",
            sa.String(length=24),
            nullable=False,
            server_default="open",
        ),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["run_id"], ["normalization_runs.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint(
            "severity IN ('info','warning','error')",
            name="ck_normalization_exceptions_severity",
        ),
        sa.CheckConstraint(
            "resolution_status IN ('open','acknowledged','resolved')",
            name="ck_normalization_exceptions_resolution_status",
        ),
    )
    op.create_index(
        "idx_normalization_exceptions_run",
        "normalization_exceptions",
        ["tenant_id", "run_id", "created_at"],
    )
    op.create_index(
        "idx_normalization_exceptions_severity",
        "normalization_exceptions",
        ["tenant_id", "run_id", "severity"],
    )

    op.create_table(
        "normalization_evidence_links",
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
        sa.Column("run_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("normalized_line_type", sa.String(length=32), nullable=False),
        sa.Column("normalized_line_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("evidence_type", sa.String(length=64), nullable=False),
        sa.Column("evidence_ref", sa.Text(), nullable=False),
        sa.Column("evidence_label", sa.String(length=255), nullable=False),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["run_id"], ["normalization_runs.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint(
            "normalized_line_type IN ('payroll_line','gl_line')",
            name="ck_normalization_evidence_links_line_type",
        ),
        sa.CheckConstraint(
            "evidence_type IN ('source_row','source_file','raw_payload_block','import_artifact')",
            name="ck_normalization_evidence_links_evidence_type",
        ),
    )
    op.create_index(
        "idx_normalization_evidence_links_run_line",
        "normalization_evidence_links",
        ["tenant_id", "run_id", "normalized_line_id"],
    )
    op.create_index(
        "idx_normalization_evidence_links_run",
        "normalization_evidence_links",
        ["tenant_id", "run_id", "created_at"],
    )

    rls_tables = [
        "normalization_sources",
        "normalization_source_versions",
        "normalization_mappings",
        "normalization_runs",
        "payroll_normalized_lines",
        "gl_normalized_lines",
        "normalization_exceptions",
        "normalization_evidence_links",
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
        "normalization_sources",
        "normalization_source_versions",
        "normalization_mappings",
        "normalization_runs",
        "payroll_normalized_lines",
        "gl_normalized_lines",
        "normalization_exceptions",
        "normalization_evidence_links",
    ]
    for table_name in append_only_tables:
        op.execute(drop_trigger_sql(table_name))
        op.execute(create_trigger_sql(table_name))


def downgrade() -> None:
    op.execute(
        "DROP TRIGGER IF EXISTS trg_normalization_source_versions_validate_supersession "
        "ON normalization_source_versions"
    )
    op.execute("DROP FUNCTION IF EXISTS normalization_source_versions_validate_supersession()")

    drop_order = [
        "normalization_evidence_links",
        "normalization_exceptions",
        "gl_normalized_lines",
        "payroll_normalized_lines",
        "normalization_runs",
        "normalization_mappings",
        "normalization_source_versions",
        "normalization_sources",
    ]
    for table_name in drop_order:
        op.execute(drop_trigger_sql(table_name))
        op.drop_table(table_name)
