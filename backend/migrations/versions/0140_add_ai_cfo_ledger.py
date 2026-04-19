"""add ai cfo ledger

Revision ID: 0140_add_ai_cfo_ledger
Revises: 0139_approval_sla_breach_runs
Create Date: 2026-04-16 19:20:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0140_add_ai_cfo_ledger"
down_revision: str | None = "0139_approval_sla_breach_runs"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "ai_cfo_ledger",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("feature", sa.String(length=64), nullable=False),
        sa.Column("provider", sa.String(length=32), nullable=False),
        sa.Column("model", sa.String(length=64), nullable=False),
        sa.Column("prompt_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("completion_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("cost_usd", sa.Numeric(10, 6), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["tenant_id"], ["iam_tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_ai_cfo_ledger_tenant_created",
        "ai_cfo_ledger",
        ["tenant_id", "created_at"],
        unique=False,
    )
    op.create_index(
        "ix_ai_cfo_ledger_tenant_provider",
        "ai_cfo_ledger",
        ["tenant_id", "provider"],
        unique=False,
    )
    op.create_table(
        "ai_cfo_narrative_blocks",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("provider", sa.String(length=32), nullable=False),
        sa.Column("llm_model", sa.String(length=64), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("highlights_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("drivers_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("risks_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("actions_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("fact_basis_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["created_by"], ["iam_users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["tenant_id"], ["iam_tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_ai_cfo_narrative_blocks_tenant_created",
        "ai_cfo_narrative_blocks",
        ["tenant_id", "created_at"],
        unique=False,
    )
    op.create_index(
        "ix_ai_cfo_narrative_blocks_tenant_provider",
        "ai_cfo_narrative_blocks",
        ["tenant_id", "provider"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_ai_cfo_narrative_blocks_tenant_provider",
        table_name="ai_cfo_narrative_blocks",
    )
    op.drop_index(
        "ix_ai_cfo_narrative_blocks_tenant_created",
        table_name="ai_cfo_narrative_blocks",
    )
    op.drop_table("ai_cfo_narrative_blocks")
    op.drop_index("ix_ai_cfo_ledger_tenant_provider", table_name="ai_cfo_ledger")
    op.drop_index("ix_ai_cfo_ledger_tenant_created", table_name="ai_cfo_ledger")
    op.drop_table("ai_cfo_ledger")
