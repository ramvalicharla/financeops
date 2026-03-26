"""ai invoice classifier module.

Revision ID: 0079_invoice_classifier
Revises: 0078_prepaid_expenses
Create Date: 2026-03-26
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

from financeops.db.append_only import append_only_function_sql, create_trigger_sql, drop_trigger_sql

revision: str = "0079_invoice_classifier"
down_revision: str | None = "0078_prepaid_expenses"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _tenant_expr() -> str:
    return (
        "COALESCE(NULLIF(current_setting('app.tenant_id', true), ''), "
        "NULLIF(current_setting('app.current_tenant_id', true), ''))::uuid"
    )


def _enable_tenant_rls(table_name: str) -> None:
    op.execute(f"ALTER TABLE {table_name} ENABLE ROW LEVEL SECURITY")
    op.execute(f"ALTER TABLE {table_name} FORCE ROW LEVEL SECURITY")
    op.execute(
        f"CREATE POLICY {table_name}_tenant_isolation ON {table_name} "
        f"USING (tenant_id = {_tenant_expr()})"
    )


def upgrade() -> None:
    op.create_table(
        "invoice_classifications",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False, server_default=sa.text("gen_random_uuid()")),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("entity_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("invoice_number", sa.String(length=200), nullable=False),
        sa.Column("vendor_name", sa.String(length=300), nullable=True),
        sa.Column("invoice_date", sa.Date(), nullable=True),
        sa.Column("invoice_amount", sa.Numeric(20, 4), nullable=False),
        sa.Column("line_description", sa.Text(), nullable=True),
        sa.Column("classification", sa.String(length=20), nullable=False),
        sa.Column("confidence", sa.Numeric(5, 4), nullable=False),
        sa.Column("classification_method", sa.String(length=20), nullable=False),
        sa.Column("rule_matched", sa.String(length=200), nullable=True),
        sa.Column("ai_reasoning", sa.Text(), nullable=True),
        sa.Column("requires_human_review", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("human_reviewed_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("human_reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("human_override", sa.String(length=20), nullable=True),
        sa.Column("routing_action", sa.String(length=20), nullable=True),
        sa.Column("routed_record_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["tenant_id"], ["iam_tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["entity_id"], ["cp_entities.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["human_reviewed_by"], ["iam_users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_invoice_classifications_tenant_id", "invoice_classifications", ["tenant_id"], unique=False)
    op.create_index("idx_invoice_classifications_entity_id", "invoice_classifications", ["entity_id"], unique=False)
    op.create_index(
        "idx_invoice_classifications_requires_human_review",
        "invoice_classifications",
        ["requires_human_review"],
        unique=False,
    )
    op.create_index("idx_invoice_classifications_routing_action", "invoice_classifications", ["routing_action"], unique=False)
    op.create_index("idx_invoice_classifications_classification", "invoice_classifications", ["classification"], unique=False)

    op.create_table(
        "classification_rules",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False, server_default=sa.text("gen_random_uuid()")),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("rule_name", sa.String(length=200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("pattern_type", sa.String(length=30), nullable=False),
        sa.Column("pattern_value", sa.String(length=500), nullable=False),
        sa.Column("amount_min", sa.Numeric(20, 4), nullable=True),
        sa.Column("amount_max", sa.Numeric(20, 4), nullable=True),
        sa.Column("classification", sa.String(length=20), nullable=False),
        sa.Column("confidence", sa.Numeric(5, 4), nullable=False),
        sa.Column("priority", sa.Integer(), nullable=False, server_default=sa.text("100")),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["tenant_id"], ["iam_tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_classification_rules_tenant_id", "classification_rules", ["tenant_id"], unique=False)
    op.create_index("idx_classification_rules_priority", "classification_rules", ["priority"], unique=False)
    op.create_index("idx_classification_rules_is_active", "classification_rules", ["is_active"], unique=False)

    _enable_tenant_rls("invoice_classifications")
    _enable_tenant_rls("classification_rules")

    op.execute(sa.text(append_only_function_sql()))
    op.execute(sa.text(create_trigger_sql("invoice_classifications")))


def downgrade() -> None:
    op.execute(sa.text(drop_trigger_sql("invoice_classifications")))

    op.drop_index("idx_classification_rules_is_active", table_name="classification_rules")
    op.drop_index("idx_classification_rules_priority", table_name="classification_rules")
    op.drop_index("idx_classification_rules_tenant_id", table_name="classification_rules")
    op.drop_table("classification_rules")

    op.drop_index("idx_invoice_classifications_classification", table_name="invoice_classifications")
    op.drop_index("idx_invoice_classifications_routing_action", table_name="invoice_classifications")
    op.drop_index("idx_invoice_classifications_requires_human_review", table_name="invoice_classifications")
    op.drop_index("idx_invoice_classifications_entity_id", table_name="invoice_classifications")
    op.drop_index("idx_invoice_classifications_tenant_id", table_name="invoice_classifications")
    op.drop_table("invoice_classifications")
