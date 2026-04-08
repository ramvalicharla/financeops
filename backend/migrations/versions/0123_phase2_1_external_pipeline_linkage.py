"""phase2.1 external pipeline linkage

Revision ID: 0123_phase2_1_ext_linkage
Revises: 0122_phase2_governance_layer
Create Date: 2026-04-08 23:15:00.000000

"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision: str = "0123_phase2_1_ext_linkage"
down_revision: Union[str, None] = "0122_phase2_governance_layer"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _add_linkage(table_name: str) -> None:
    op.add_column(table_name, sa.Column("created_by_intent_id", UUID(as_uuid=True), nullable=True))
    op.add_column(table_name, sa.Column("recorded_by_job_id", UUID(as_uuid=True), nullable=True))
    op.create_index(f"ix_{table_name}_created_by_intent_id", table_name, ["created_by_intent_id"])
    op.create_index(f"ix_{table_name}_recorded_by_job_id", table_name, ["recorded_by_job_id"])
    op.create_foreign_key(
        f"fk_{table_name}_created_by_intent_id",
        table_name,
        "canonical_intents",
        ["created_by_intent_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_foreign_key(
        f"fk_{table_name}_recorded_by_job_id",
        table_name,
        "canonical_jobs",
        ["recorded_by_job_id"],
        ["id"],
        ondelete="SET NULL",
    )


def _drop_linkage(table_name: str) -> None:
    op.drop_constraint(f"fk_{table_name}_recorded_by_job_id", table_name, type_="foreignkey")
    op.drop_constraint(f"fk_{table_name}_created_by_intent_id", table_name, type_="foreignkey")
    op.drop_index(f"ix_{table_name}_recorded_by_job_id", table_name=table_name)
    op.drop_index(f"ix_{table_name}_created_by_intent_id", table_name=table_name)
    op.drop_column(table_name, "recorded_by_job_id")
    op.drop_column(table_name, "created_by_intent_id")


def upgrade() -> None:
    for table_name in ("external_sync_runs", "external_raw_snapshots", "normalization_runs"):
        _add_linkage(table_name)


def downgrade() -> None:
    for table_name in ("normalization_runs", "external_raw_snapshots", "external_sync_runs"):
        _drop_linkage(table_name)
