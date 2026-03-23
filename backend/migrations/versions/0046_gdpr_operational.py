"""GDPR operational controls for consent, data requests, and breach records.

Revision ID: 0046_gdpr_operational
Revises: 0045_compliance_controls
Create Date: 2026-03-23 20:45:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

from financeops.db.append_only import append_only_function_sql, create_trigger_sql, drop_trigger_sql

revision: str = "0046_gdpr_operational"
down_revision: str | None = "0045_compliance_controls"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _table_exists(table_name: str) -> bool:
    bind = op.get_bind()
    value = bind.execute(
        sa.text("SELECT to_regclass(:table_name)"),
        {"table_name": f"public.{table_name}"},
    ).scalar_one_or_none()
    return value is not None


def _index_exists(index_name: str) -> bool:
    bind = op.get_bind()
    value = bind.execute(
        sa.text(
            """
            SELECT 1
            FROM pg_class c
            JOIN pg_namespace n ON n.oid = c.relnamespace
            WHERE c.relkind = 'i'
              AND n.nspname = 'public'
              AND c.relname = :index_name
            LIMIT 1
            """
        ),
        {"index_name": index_name},
    ).scalar_one_or_none()
    return value is not None


def _policy_exists(table_name: str, policy_name: str) -> bool:
    bind = op.get_bind()
    value = bind.execute(
        sa.text(
            """
            SELECT 1
            FROM pg_policies
            WHERE schemaname = 'public'
              AND tablename = :table_name
              AND policyname = :policy_name
            LIMIT 1
            """
        ),
        {"table_name": table_name, "policy_name": policy_name},
    ).scalar_one_or_none()
    return value is not None


def _enable_rls_with_policies(table_name: str) -> None:
    op.execute(f"ALTER TABLE {table_name} ENABLE ROW LEVEL SECURITY")
    op.execute(f"ALTER TABLE {table_name} FORCE ROW LEVEL SECURITY")
    if not _policy_exists(table_name, "tenant_isolation"):
        op.execute(
            f"CREATE POLICY tenant_isolation ON {table_name} "
            "USING (tenant_id = COALESCE(NULLIF(current_setting('app.tenant_id', true), ''), NULLIF(current_setting('app.current_tenant_id', true), ''))::uuid)"
        )


def upgrade() -> None:
    if not _table_exists("gdpr_consent_records"):
        op.create_table(
            "gdpr_consent_records",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False, server_default=sa.text("gen_random_uuid()")),
            sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("consent_type", sa.String(length=50), nullable=False),
            sa.Column("granted", sa.Boolean(), nullable=False),
            sa.Column("granted_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("withdrawn_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("ip_address", sa.String(length=45), nullable=True),
            sa.Column("user_agent", sa.String(length=500), nullable=True),
            sa.Column("lawful_basis", sa.String(length=50), nullable=False, server_default=sa.text("'consent'")),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
            sa.ForeignKeyConstraint(["user_id"], ["iam_users.id"], ondelete="CASCADE"),
            sa.CheckConstraint(
                "consent_type IN ('analytics','marketing','ai_processing','data_sharing','performance_monitoring')",
                name="ck_gdpr_consent_type",
            ),
            sa.CheckConstraint(
                "lawful_basis IN ('consent','legitimate_interest','contract','legal_obligation')",
                name="ck_gdpr_lawful_basis",
            ),
            sa.UniqueConstraint("tenant_id", "user_id", "consent_type", name="uq_gdpr_consent_tenant_user_type"),
        )

    if not _table_exists("gdpr_data_requests"):
        op.create_table(
            "gdpr_data_requests",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False, server_default=sa.text("gen_random_uuid()")),
            sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("request_type", sa.String(length=30), nullable=False),
            sa.Column("status", sa.String(length=20), nullable=False, server_default=sa.text("'received'")),
            sa.Column("requested_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
            sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("rejection_reason", sa.Text(), nullable=True),
            sa.Column("export_url", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
            sa.CheckConstraint(
                "request_type IN ('portability','erasure','access','rectification','restriction','objection')",
                name="ck_gdpr_data_request_type",
            ),
            sa.CheckConstraint(
                "status IN ('received','processing','completed','rejected')",
                name="ck_gdpr_data_request_status",
            ),
        )

    if not _table_exists("gdpr_breach_records"):
        op.create_table(
            "gdpr_breach_records",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False, server_default=sa.text("gen_random_uuid()")),
            sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("breach_type", sa.String(length=50), nullable=False),
            sa.Column("description", sa.Text(), nullable=False),
            sa.Column("affected_user_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
            sa.Column("affected_data_types", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'[]'::jsonb")),
            sa.Column("discovered_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("reported_to_dpa_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("notified_users_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("severity", sa.String(length=20), nullable=False),
            sa.Column("status", sa.String(length=20), nullable=False, server_default=sa.text("'open'")),
            sa.Column("remediation_notes", sa.Text(), nullable=True),
            sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
            sa.ForeignKeyConstraint(["created_by"], ["iam_users.id"], ondelete="RESTRICT"),
            sa.CheckConstraint(
                "breach_type IN ('unauthorized_access','data_loss','ransomware','accidental_disclosure','other')",
                name="ck_gdpr_breach_type",
            ),
            sa.CheckConstraint("severity IN ('low','medium','high','critical')", name="ck_gdpr_breach_severity"),
            sa.CheckConstraint("status IN ('open','reported','closed')", name="ck_gdpr_breach_status"),
        )

    if not _index_exists("idx_gdpr_consent_tenant_user_type"):
        op.execute("CREATE INDEX idx_gdpr_consent_tenant_user_type ON gdpr_consent_records (tenant_id, user_id, consent_type)")
    if not _index_exists("idx_gdpr_data_requests_tenant_user_created"):
        op.execute("CREATE INDEX idx_gdpr_data_requests_tenant_user_created ON gdpr_data_requests (tenant_id, user_id, created_at DESC)")
    if not _index_exists("idx_gdpr_breach_tenant_discovered"):
        op.execute("CREATE INDEX idx_gdpr_breach_tenant_discovered ON gdpr_breach_records (tenant_id, discovered_at DESC)")

    for table_name in ("gdpr_consent_records", "gdpr_data_requests", "gdpr_breach_records"):
        if _table_exists(table_name):
            _enable_rls_with_policies(table_name)

    for append_only_table in ("gdpr_data_requests", "gdpr_breach_records"):
        if _table_exists(append_only_table):
            op.execute(append_only_function_sql())
            op.execute(drop_trigger_sql(append_only_table))
            op.execute(create_trigger_sql(append_only_table))


def downgrade() -> None:
    for table_name in ("gdpr_data_requests", "gdpr_breach_records"):
        if _table_exists(table_name):
            op.execute(drop_trigger_sql(table_name))
    if _index_exists("idx_gdpr_breach_tenant_discovered") and _table_exists("gdpr_breach_records"):
        op.drop_index("idx_gdpr_breach_tenant_discovered", table_name="gdpr_breach_records")
    if _index_exists("idx_gdpr_data_requests_tenant_user_created") and _table_exists("gdpr_data_requests"):
        op.drop_index("idx_gdpr_data_requests_tenant_user_created", table_name="gdpr_data_requests")
    if _index_exists("idx_gdpr_consent_tenant_user_type") and _table_exists("gdpr_consent_records"):
        op.drop_index("idx_gdpr_consent_tenant_user_type", table_name="gdpr_consent_records")
    if _table_exists("gdpr_breach_records"):
        op.drop_table("gdpr_breach_records")
    if _table_exists("gdpr_data_requests"):
        op.drop_table("gdpr_data_requests")
    if _table_exists("gdpr_consent_records"):
        op.drop_table("gdpr_consent_records")

