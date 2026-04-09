"""Phase 4.1 definition linkage

Revision ID: 0128_phase4_1_definition_linkage
Revises: 0127_phase4_control_plane_evidence
Create Date: 2026-04-09 00:00:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "0128_phase4_1_definition_linkage"
down_revision = "0127_phase4_control_plane"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "report_definitions",
        sa.Column("created_by_intent_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.add_column(
        "report_definitions",
        sa.Column("recorded_by_job_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.add_column(
        "board_pack_definitions",
        sa.Column("created_by_intent_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.add_column(
        "board_pack_definitions",
        sa.Column("recorded_by_job_id", postgresql.UUID(as_uuid=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("board_pack_definitions", "recorded_by_job_id")
    op.drop_column("board_pack_definitions", "created_by_intent_id")
    op.drop_column("report_definitions", "recorded_by_job_id")
    op.drop_column("report_definitions", "created_by_intent_id")
