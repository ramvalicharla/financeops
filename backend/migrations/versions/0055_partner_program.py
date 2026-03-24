"""Partner program tables for referrals and commissions.

Revision ID: 0055_partner_program
Revises: 0054_white_label
Create Date: 2026-03-24 22:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

from financeops.db.append_only import append_only_function_sql, create_trigger_sql, drop_trigger_sql

revision: str = "0055_partner_program"
down_revision: str | None = "0054_white_label"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _table_exists(table_name: str) -> bool:
    bind = op.get_bind()
    value = bind.execute(
        sa.text("SELECT to_regclass(:table_name)"),
        {"table_name": f"public.{table_name}"},
    ).scalar_one_or_none()
    return value is not None


def _index_exists(index_name: str) -> bool:
    bind = op.get_bind()
    value = bind.execute(
        sa.text(
            """
            SELECT 1
            FROM pg_class c
            JOIN pg_namespace n ON n.oid = c.relnamespace
            WHERE c.relkind = 'i'
              AND n.nspname = 'public'
              AND c.relname = :index_name
            LIMIT 1
            """
        ),
        {"index_name": index_name},
    ).scalar_one_or_none()
    return value is not None


def _policy_exists(table_name: str, policy_name: str) -> bool:
    bind = op.get_bind()
    value = bind.execute(
        sa.text(
            """
            SELECT 1
            FROM pg_policies
            WHERE schemaname = 'public'
              AND tablename = :table_name
              AND policyname = :policy_name
            LIMIT 1
            """
        ),
        {"table_name": table_name, "policy_name": policy_name},
    ).scalar_one_or_none()
    return value is not None


def _tenant_expr() -> str:
    return (
        "COALESCE(NULLIF(current_setting('app.tenant_id', true), ''), "
        "NULLIF(current_setting('app.current_tenant_id', true), ''))::uuid"
    )


def _enable_rls(table_name: str) -> None:
    op.execute(f"ALTER TABLE {table_name} ENABLE ROW LEVEL SECURITY")
    op.execute(f"ALTER TABLE {table_name} FORCE ROW LEVEL SECURITY")
    if not _policy_exists(table_name, "tenant_isolation"):
        op.execute(
            f"CREATE POLICY tenant_isolation ON {table_name} "
            f"USING (tenant_id = {_tenant_expr()})"
        )


def _enable_commission_rls(table_name: str) -> None:
    op.execute(f"ALTER TABLE {table_name} ENABLE ROW LEVEL SECURITY")
    op.execute(f"ALTER TABLE {table_name} FORCE ROW LEVEL SECURITY")
    if not _policy_exists(table_name, "tenant_isolation"):
        op.execute(
            f"CREATE POLICY tenant_isolation ON {table_name} USING ("
            "partner_id IN ("
            "SELECT p.id FROM partner_profiles p "
            f"WHERE p.tenant_id = {_tenant_expr()}"
            ")"
            ")"
        )


def upgrade() -> None:
    if not _table_exists("partner_profiles"):
        op.create_table(
            "partner_profiles",
            sa.Column(
                "id",
                postgresql.UUID(as_uuid=True),
                primary_key=True,
                nullable=False,
                server_default=sa.text("gen_random_uuid()"),
            ),
            sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False, unique=True),
            sa.Column(
                "partner_tier",
                sa.String(length=20),
                nullable=False,
                server_default=sa.text("'referral'"),
            ),
            sa.Column("company_name", sa.String(length=300), nullable=False),
            sa.Column("contact_email", sa.String(length=300), nullable=False),
            sa.Column("website_url", sa.Text(), nullable=True),
            sa.Column("partner_code", sa.String(length=20), nullable=False, unique=True),
            sa.Column("commission_rate_pct", sa.Numeric(5, 4), nullable=False),
            sa.Column("total_referrals", sa.Integer(), nullable=False, server_default=sa.text("0")),
            sa.Column(
                "total_commissions_earned",
                sa.Numeric(20, 2),
                nullable=False,
                server_default=sa.text("0"),
            ),
            sa.Column("stripe_account_id", sa.String(length=100), nullable=True),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
            sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
            sa.CheckConstraint(
                "partner_tier IN ('referral','reseller','technology')",
                name="ck_partner_profiles_tier",
            ),
            sa.UniqueConstraint("tenant_id", name="uq_partner_profiles_tenant"),
            sa.UniqueConstraint("partner_code", name="uq_partner_profiles_code"),
        )

    if not _table_exists("referral_tracking"):
        op.create_table(
            "referral_tracking",
            sa.Column(
                "id",
                postgresql.UUID(as_uuid=True),
                primary_key=True,
                nullable=False,
                server_default=sa.text("gen_random_uuid()"),
            ),
            sa.Column(
                "partner_id",
                postgresql.UUID(as_uuid=True),
                sa.ForeignKey("partner_profiles.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column(
                "referred_tenant_id",
                postgresql.UUID(as_uuid=True),
                sa.ForeignKey("iam_tenants.id", ondelete="SET NULL"),
                nullable=True,
            ),
            sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("referral_code", sa.String(length=20), nullable=False),
            sa.Column("referral_email", sa.String(length=300), nullable=True),
            sa.Column(
                "status",
                sa.String(length=20),
                nullable=False,
                server_default=sa.text("'clicked'"),
            ),
            sa.Column("clicked_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
            sa.Column("signed_up_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("converted_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("first_payment_amount", sa.Numeric(20, 2), nullable=True),
            sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
            sa.CheckConstraint(
                "status IN ('clicked','signed_up','converted','churned','expired')",
                name="ck_referral_tracking_status",
            ),
            sa.CheckConstraint(
                "expires_at > created_at",
                name="ck_referral_tracking_expiry_gt_created",
            ),
        )

    if not _table_exists("partner_commissions"):
        op.create_table(
            "partner_commissions",
            sa.Column(
                "id",
                postgresql.UUID(as_uuid=True),
                primary_key=True,
                nullable=False,
                server_default=sa.text("gen_random_uuid()"),
            ),
            sa.Column(
                "partner_id",
                postgresql.UUID(as_uuid=True),
                sa.ForeignKey("partner_profiles.id", ondelete="RESTRICT"),
                nullable=False,
            ),
            sa.Column(
                "referral_id",
                postgresql.UUID(as_uuid=True),
                sa.ForeignKey("referral_tracking.id", ondelete="RESTRICT"),
                nullable=False,
            ),
            sa.Column("referred_tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("commission_type", sa.String(length=20), nullable=False),
            sa.Column("payment_amount", sa.Numeric(20, 2), nullable=False),
            sa.Column("commission_rate", sa.Numeric(5, 4), nullable=False),
            sa.Column("commission_amount", sa.Numeric(20, 2), nullable=False),
            sa.Column(
                "status",
                sa.String(length=20),
                nullable=False,
                server_default=sa.text("'pending'"),
            ),
            sa.Column("period", sa.String(length=7), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
            sa.CheckConstraint(
                "commission_type IN ('first_payment','recurring','technology_rev_share')",
                name="ck_partner_commissions_type",
            ),
            sa.CheckConstraint(
                "status IN ('pending','approved','paid','cancelled')",
                name="ck_partner_commissions_status",
            ),
        )

    if not _index_exists("idx_referral_tracking_referral_code"):
        op.execute("CREATE INDEX idx_referral_tracking_referral_code ON referral_tracking (referral_code)")
    if not _index_exists("idx_referral_tracking_partner_status"):
        op.execute("CREATE INDEX idx_referral_tracking_partner_status ON referral_tracking (partner_id, status)")
    if not _index_exists("idx_partner_commissions_partner_status_created"):
        op.execute(
            "CREATE INDEX idx_partner_commissions_partner_status_created "
            "ON partner_commissions (partner_id, status, created_at DESC)"
        )

    if _table_exists("partner_profiles"):
        _enable_rls("partner_profiles")
    if _table_exists("referral_tracking"):
        _enable_rls("referral_tracking")
    if _table_exists("partner_commissions"):
        _enable_commission_rls("partner_commissions")

    if _table_exists("partner_commissions"):
        op.execute(append_only_function_sql())
        op.execute(drop_trigger_sql("partner_commissions"))
        op.execute(create_trigger_sql("partner_commissions"))


def downgrade() -> None:
    if _table_exists("partner_commissions"):
        op.execute(drop_trigger_sql("partner_commissions"))

    if _index_exists("idx_partner_commissions_partner_status_created") and _table_exists("partner_commissions"):
        op.drop_index("idx_partner_commissions_partner_status_created", table_name="partner_commissions")
    if _index_exists("idx_referral_tracking_partner_status") and _table_exists("referral_tracking"):
        op.drop_index("idx_referral_tracking_partner_status", table_name="referral_tracking")
    if _index_exists("idx_referral_tracking_referral_code") and _table_exists("referral_tracking"):
        op.drop_index("idx_referral_tracking_referral_code", table_name="referral_tracking")

    if _table_exists("partner_commissions"):
        op.drop_table("partner_commissions")
    if _table_exists("referral_tracking"):
        op.drop_table("referral_tracking")
    if _table_exists("partner_profiles"):
        op.drop_table("partner_profiles")

