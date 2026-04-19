"""budget workflow status events

Revision ID: 0142_budget_workflow
Revises: 0141_tz_asia_kolkata
Create Date: 2026-04-16 20:40:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "0142_budget_workflow"
down_revision = "0141_tz_asia_kolkata"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("UPDATE budget_versions SET status = 'board_approved' WHERE status = 'approved'")
    op.drop_constraint("ck_budget_versions_status", "budget_versions", type_="check")
    op.create_check_constraint(
        "ck_budget_versions_status",
        "budget_versions",
        "status IN ('draft','submitted','cfo_approved','board_approved','superseded')",
    )
    op.create_table(
        "budget_version_status_events",
        sa.Column("budget_version_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("from_status", sa.String(length=20), nullable=True),
        sa.Column("to_status", sa.String(length=20), nullable=False),
        sa.Column("acted_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["acted_by"], ["iam_users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(
            ["budget_version_id"],
            ["budget_versions.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "idx_budget_status_events_version",
        "budget_version_status_events",
        ["tenant_id", "budget_version_id", "created_at"],
    )
    op.create_index(
        "idx_budget_status_events_status",
        "budget_version_status_events",
        ["tenant_id", "to_status", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("idx_budget_status_events_status", table_name="budget_version_status_events")
    op.drop_index("idx_budget_status_events_version", table_name="budget_version_status_events")
    op.drop_table("budget_version_status_events")
    op.drop_constraint("ck_budget_versions_status", "budget_versions", type_="check")
    op.create_check_constraint(
        "ck_budget_versions_status",
        "budget_versions",
        "status IN ('draft','submitted','approved','superseded')",
    )
    op.execute("UPDATE budget_versions SET status = 'approved' WHERE status = 'board_approved'")
