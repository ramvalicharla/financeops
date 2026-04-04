"""allow_expense_claim_updates

Revision ID: 0114_expense_claims_mutable
Revises: 0113_checklist_run_mutable
Create Date: 2026-04-03

Expense claims are mutable through approval and tax enrichment workflows.
Drop default append-only trigger on expense_claims.
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

from financeops.db.append_only import (
    append_only_function_sql,
    create_trigger_sql,
    drop_trigger_sql,
)


revision = "0114_expense_claims_mutable"
down_revision = "0113_checklist_run_mutable"
branch_labels = None
depends_on = None


def _table_exists(table_name: str) -> bool:
    bind = op.get_bind()
    query = sa.text(
        """
        SELECT 1
        FROM information_schema.tables
        WHERE table_schema = 'public'
          AND table_name = :table_name
        LIMIT 1
        """
    )
    return bind.execute(query, {"table_name": table_name}).scalar() is not None


def upgrade() -> None:
    if _table_exists("expense_claims"):
        op.execute(drop_trigger_sql("expense_claims"))


def downgrade() -> None:
    if _table_exists("expense_claims"):
        op.execute(append_only_function_sql())
        op.execute(drop_trigger_sql("expense_claims"))
        op.execute(create_trigger_sql("expense_claims"))

