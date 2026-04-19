"""set default timezone asia kolkata

Revision ID: 0141_tz_asia_kolkata
Revises: 0140_add_ai_cfo_ledger
Create Date: 2026-04-16 19:50:00.000000
"""

from __future__ import annotations

from alembic import op


revision = "0141_tz_asia_kolkata"
down_revision = "0140_add_ai_cfo_ledger"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE iam_tenants ALTER COLUMN timezone SET DEFAULT 'Asia/Kolkata'")


def downgrade() -> None:
    op.execute("ALTER TABLE iam_tenants ALTER COLUMN timezone SET DEFAULT 'UTC'")
