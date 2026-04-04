"""allow_forecast_run_updates

Revision ID: 0115_forecast_runs_mutable
Revises: 0114_expense_claims_mutable
Create Date: 2026-04-03

Forecast runs transition status during publish/approval workflows, so the
default append-only trigger on forecast_runs must be removed.
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

from financeops.db.append_only import (
    append_only_function_sql,
    create_trigger_sql,
    drop_trigger_sql,
)


revision = "0115_forecast_runs_mutable"
down_revision = "0114_expense_claims_mutable"
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
    if _table_exists("forecast_runs"):
        op.execute(drop_trigger_sql("forecast_runs"))


def downgrade() -> None:
    if _table_exists("forecast_runs"):
        op.execute(append_only_function_sql())
        op.execute(drop_trigger_sql("forecast_runs"))
        op.execute(create_trigger_sql("forecast_runs"))

