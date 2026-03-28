"""erp_webhook_event_ingest

Revision ID: 0097_erp_webhook_event_ingest
Revises: 0092_erp_push_runs_events
Create Date: 2026-03-29

Creates:
  erp_webhook_events
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision: str = "0097_erp_webhook_event_ingest"
down_revision: str | None = "0092_erp_push_runs_events"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "erp_webhook_events",
        sa.Column("id", UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", UUID(as_uuid=True), nullable=False),
        sa.Column("chain_hash", sa.String(length=64), nullable=False),
        sa.Column("previous_hash", sa.String(length=64), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("connector_type", sa.String(length=32), nullable=False),
        sa.Column("message_id", sa.String(length=255), nullable=False),
        sa.Column("event_type", sa.String(length=128), nullable=False),
        sa.Column("canonical_event_type", sa.String(length=64), nullable=True),
        sa.Column("payload", JSONB, nullable=False),
        sa.Column("raw_headers", JSONB, nullable=True),
        sa.Column("signature_verified", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("processed", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("processing_error", sa.Text(), nullable=True),
        sa.Column("dead_lettered", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("dead_letter_reason", sa.Text(), nullable=True),
        sa.Column(
            "received_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "tenant_id",
            "connector_type",
            "message_id",
            name="uq_erp_webhook_events_message_id",
        ),
    )

    op.create_index(
        "ix_erp_webhook_events_tenant_id",
        "erp_webhook_events",
        ["tenant_id"],
    )
    op.create_index(
        "ix_erp_webhook_events_connector_type",
        "erp_webhook_events",
        ["tenant_id", "connector_type"],
    )
    op.create_index(
        "ix_erp_webhook_events_processed",
        "erp_webhook_events",
        ["tenant_id", "processed", "received_at"],
    )
    op.create_index(
        "ix_erp_webhook_events_canonical_type",
        "erp_webhook_events",
        ["tenant_id", "canonical_event_type"],
    )
    op.create_index(
        "ix_erp_webhook_events_dead_lettered",
        "erp_webhook_events",
        ["tenant_id", "dead_lettered"],
        postgresql_where=sa.text("dead_lettered = true"),
    )

    op.execute("ALTER TABLE erp_webhook_events ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE erp_webhook_events FORCE ROW LEVEL SECURITY")
    op.execute(
        "CREATE POLICY tenant_isolation ON erp_webhook_events "
        "USING (tenant_id = COALESCE(current_setting('app.tenant_id', true), "
        "current_setting('app.current_tenant_id', true))::uuid)"
    )


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS tenant_isolation ON erp_webhook_events")

    op.drop_index(
        "ix_erp_webhook_events_dead_lettered",
        table_name="erp_webhook_events",
    )
    op.drop_index(
        "ix_erp_webhook_events_canonical_type",
        table_name="erp_webhook_events",
    )
    op.drop_index(
        "ix_erp_webhook_events_processed",
        table_name="erp_webhook_events",
    )
    op.drop_index(
        "ix_erp_webhook_events_connector_type",
        table_name="erp_webhook_events",
    )
    op.drop_index(
        "ix_erp_webhook_events_tenant_id",
        table_name="erp_webhook_events",
    )
    op.drop_table("erp_webhook_events")
