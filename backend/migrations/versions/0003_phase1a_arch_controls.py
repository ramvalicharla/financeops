"""Phase 1A architecture controls: append-only DB enforcement

Revision ID: 0003_phase1a
Revises: 0002_phase1
Create Date: 2026-03-06 00:00:00.000000
"""
from __future__ import annotations

from collections.abc import Sequence

from alembic import op

from financeops.db.append_only import (
    APPEND_ONLY_TRIGGER_FUNCTION,
    append_only_function_sql,
    create_trigger_sql,
    drop_trigger_sql,
)

revision: str = "0003_phase1a"
down_revision: str | None = "0002_phase1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

PHASE_1A_APPEND_ONLY_TABLES: tuple[str, ...] = (
    "audit_trail",
    "credit_transactions",
    "mis_templates",
    "mis_uploads",
    "gl_entries",
    "trial_balance_rows",
    "recon_items",
    "bank_statements",
    "bank_transactions",
    "bank_recon_items",
    "working_capital_snapshots",
    "gst_returns",
    "gst_recon_items",
    "monthend_checklists",
    "auditor_grants",
    "auditor_access_logs",
)


def upgrade() -> None:
    op.execute(append_only_function_sql())
    for table_name in PHASE_1A_APPEND_ONLY_TABLES:
        op.execute(drop_trigger_sql(table_name))
        op.execute(create_trigger_sql(table_name))


def downgrade() -> None:
    for table_name in reversed(PHASE_1A_APPEND_ONLY_TABLES):
        op.execute(drop_trigger_sql(table_name))
    op.execute(f"DROP FUNCTION IF EXISTS {APPEND_ONLY_TRIGGER_FUNCTION}()")
