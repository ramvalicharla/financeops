"""Phase 4.4 closure linkage

Revision ID: 0129_phase4_4_closure_linkage
Revises: 0128_phase4_1_definition_linkage
Create Date: 2026-04-09 00:00:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "0129_phase4_4_closure_linkage"
down_revision = "0128_phase4_1_definition_linkage"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "canonical_intents",
        sa.Column("parent_intent_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_canonical_intents_parent_intent_id",
        "canonical_intents",
        "canonical_intents",
        ["parent_intent_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(
        "ix_canonical_intents_parent_intent_id",
        "canonical_intents",
        ["parent_intent_id"],
        unique=False,
    )

    op.add_column(
        "board_pack_section_definitions",
        sa.Column("created_by_intent_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.add_column(
        "board_pack_section_definitions",
        sa.Column("recorded_by_job_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.add_column(
        "narrative_templates",
        sa.Column("created_by_intent_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.add_column(
        "narrative_templates",
        sa.Column("recorded_by_job_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.add_column(
        "board_pack_inclusion_rules",
        sa.Column("created_by_intent_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.add_column(
        "board_pack_inclusion_rules",
        sa.Column("recorded_by_job_id", postgresql.UUID(as_uuid=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("board_pack_inclusion_rules", "recorded_by_job_id")
    op.drop_column("board_pack_inclusion_rules", "created_by_intent_id")
    op.drop_column("narrative_templates", "recorded_by_job_id")
    op.drop_column("narrative_templates", "created_by_intent_id")
    op.drop_column("board_pack_section_definitions", "recorded_by_job_id")
    op.drop_column("board_pack_section_definitions", "created_by_intent_id")

    op.drop_index("ix_canonical_intents_parent_intent_id", table_name="canonical_intents")
    op.drop_constraint("fk_canonical_intents_parent_intent_id", "canonical_intents", type_="foreignkey")
    op.drop_column("canonical_intents", "parent_intent_id")
