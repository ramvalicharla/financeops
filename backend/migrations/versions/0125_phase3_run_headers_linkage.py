"""phase3 run header linkage

Revision ID: 0125_phase3_run_header_linkage
Revises: 0124_phase3_finance_linkage
Create Date: 2026-04-09 03:20:00.000000

"""
from __future__ import annotations

import hashlib
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision: str = "0125_phase3_run_header_linkage"
down_revision: Union[str, None] = "0124_phase3_finance_linkage"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _name(prefix: str, table_name: str, suffix: str) -> str:
    digest = hashlib.md5(table_name.encode("utf-8")).hexdigest()[:8]
    return f"{prefix}_{digest}_{suffix}"


def _add_linkage(table_name: str) -> None:
    op.add_column(table_name, sa.Column("created_by_intent_id", UUID(as_uuid=True), nullable=True))
    op.add_column(table_name, sa.Column("recorded_by_job_id", UUID(as_uuid=True), nullable=True))
    op.create_index(_name("ix", table_name, "cbi"), table_name, ["created_by_intent_id"])
    op.create_index(_name("ix", table_name, "rbj"), table_name, ["recorded_by_job_id"])
    op.create_foreign_key(
        _name("fk", table_name, "cbi"),
        table_name,
        "canonical_intents",
        ["created_by_intent_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_foreign_key(
        _name("fk", table_name, "rbj"),
        table_name,
        "canonical_jobs",
        ["recorded_by_job_id"],
        ["id"],
        ondelete="SET NULL",
    )


def _drop_linkage(table_name: str) -> None:
    op.drop_constraint(_name("fk", table_name, "rbj"), table_name, type_="foreignkey")
    op.drop_constraint(_name("fk", table_name, "cbi"), table_name, type_="foreignkey")
    op.drop_index(_name("ix", table_name, "rbj"), table_name=table_name)
    op.drop_index(_name("ix", table_name, "cbi"), table_name=table_name)
    op.drop_column(table_name, "recorded_by_job_id")
    op.drop_column(table_name, "created_by_intent_id")


TABLES = (
    "far_runs",
    "prepaid_runs",
)


def upgrade() -> None:
    for table_name in TABLES:
        _add_linkage(table_name)


def downgrade() -> None:
    for table_name in reversed(TABLES):
        _drop_linkage(table_name)
