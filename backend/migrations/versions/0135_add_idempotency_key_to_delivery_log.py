"""add idempotency key to delivery log

Revision ID: 0135_delivery_log_idem
Revises: 0134_gl_src_ref_unique
Create Date: 2026-04-16 23:58:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0135_delivery_log_idem"
down_revision = "0134_gl_src_ref_unique"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "delivery_logs",
        sa.Column("idempotency_key", sa.String(length=64), nullable=True),
    )
    op.create_index(
        "idx_delivery_logs_tenant_idempotency_key",
        "delivery_logs",
        ["tenant_id", "idempotency_key"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("idx_delivery_logs_tenant_idempotency_key", table_name="delivery_logs")
    op.drop_column("delivery_logs", "idempotency_key")
