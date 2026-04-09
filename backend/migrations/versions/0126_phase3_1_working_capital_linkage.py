"""phase3.1 working capital linkage

Revision ID: 0126_phase3_1_wc_linkage
Revises: 0125_phase3_run_header_linkage
Create Date: 2026-04-09 22:15:00.000000

"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision: str = "0126_phase3_1_wc_linkage"
down_revision: Union[str, None] = "0125_phase3_run_header_linkage"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "working_capital_snapshots",
        sa.Column("created_by_intent_id", UUID(as_uuid=True), nullable=True),
    )
    op.add_column(
        "working_capital_snapshots",
        sa.Column("recorded_by_job_id", UUID(as_uuid=True), nullable=True),
    )
    op.create_index(
        "ix_working_capital_snapshots_created_by_intent_id",
        "working_capital_snapshots",
        ["created_by_intent_id"],
    )
    op.create_index(
        "ix_working_capital_snapshots_recorded_by_job_id",
        "working_capital_snapshots",
        ["recorded_by_job_id"],
    )
    op.create_foreign_key(
        "fk_working_capital_snapshots_created_by_intent_id",
        "working_capital_snapshots",
        "canonical_intents",
        ["created_by_intent_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_foreign_key(
        "fk_working_capital_snapshots_recorded_by_job_id",
        "working_capital_snapshots",
        "canonical_jobs",
        ["recorded_by_job_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint(
        "fk_working_capital_snapshots_recorded_by_job_id",
        "working_capital_snapshots",
        type_="foreignkey",
    )
    op.drop_constraint(
        "fk_working_capital_snapshots_created_by_intent_id",
        "working_capital_snapshots",
        type_="foreignkey",
    )
    op.drop_index(
        "ix_working_capital_snapshots_recorded_by_job_id",
        table_name="working_capital_snapshots",
    )
    op.drop_index(
        "ix_working_capital_snapshots_created_by_intent_id",
        table_name="working_capital_snapshots",
    )
    op.drop_column("working_capital_snapshots", "recorded_by_job_id")
    op.drop_column("working_capital_snapshots", "created_by_intent_id")
