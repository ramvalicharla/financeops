"""add tenant created composite indexes

Revision ID: 0143_tenant_created_idx
Revises: 0142_budget_workflow
Create Date: 2026-04-16 20:45:00.000000
"""

from __future__ import annotations

from alembic import op


revision = "0143_tenant_created_idx"
down_revision = "0142_budget_workflow"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index(
        "idx_bank_txns_tenant_created",
        "bank_transactions",
        ["tenant_id", "created_at"],
    )
    op.create_index(
        "idx_gst_returns_tenant_created",
        "gst_returns",
        ["tenant_id", "created_at"],
    )
    op.create_index(
        "idx_erp_sync_jobs_tenant_created",
        "erp_sync_jobs",
        ["tenant_id", "created_at"],
    )
    op.create_index(
        "idx_iam_sessions_tenant_created",
        "iam_sessions",
        ["tenant_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("idx_iam_sessions_tenant_created", table_name="iam_sessions")
    op.drop_index("idx_erp_sync_jobs_tenant_created", table_name="erp_sync_jobs")
    op.drop_index("idx_gst_returns_tenant_created", table_name="gst_returns")
    op.drop_index("idx_bank_txns_tenant_created", table_name="bank_transactions")
