"""accounting_approval_and_sla

Revision ID: 0087_accounting_approval_and_sla
Revises: 0086_accounting_jv_state_machine
Create Date: 2026-03-28

Creates:
  accounting_jv_approvals - append-only approval decisions per JV
  approval_sla_timers - mutable SLA breach tracking per JV

Seeds RBAC:
  cp_roles, cp_permissions, cp_role_permissions for accounting approval flow.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

from financeops.db.append_only import (
    append_only_function_sql,
    create_trigger_sql,
    drop_trigger_sql,
)

revision: str = "0087_accounting_approval_and_sla"
down_revision: str | None = "0086_accounting_jv_state_machine"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


_R_PREPARER = "a1000001-0000-0000-0000-000000000001"
_R_REVIEWER = "a1000001-0000-0000-0000-000000000002"
_R_SR_REVIEWER = "a1000001-0000-0000-0000-000000000003"
_R_CFO_APPROVER = "a1000001-0000-0000-0000-000000000004"
_R_ACCT_ADMIN = "a1000001-0000-0000-0000-000000000005"
_R_AUDITOR = "a1000001-0000-0000-0000-000000000006"

_P_JV_CREATE = "b2000001-0000-0000-0000-000000000001"
_P_JV_SUBMIT = "b2000001-0000-0000-0000-000000000002"
_P_JV_REVIEW = "b2000001-0000-0000-0000-000000000003"
_P_JV_APPROVE = "b2000001-0000-0000-0000-000000000004"
_P_JV_REJECT = "b2000001-0000-0000-0000-000000000005"
_P_JV_VOID = "b2000001-0000-0000-0000-000000000006"
_P_JV_VIEW = "b2000001-0000-0000-0000-000000000007"
_P_JV_EXPORT = "b2000001-0000-0000-0000-000000000008"

_RP_IDS: dict[str, str] = {
    "preparer_create": "c3000001-0000-0000-0000-000000000001",
    "preparer_submit": "c3000001-0000-0000-0000-000000000002",
    "preparer_view": "c3000001-0000-0000-0000-000000000003",
    "reviewer_review": "c3000001-0000-0000-0000-000000000004",
    "reviewer_reject": "c3000001-0000-0000-0000-000000000005",
    "reviewer_view": "c3000001-0000-0000-0000-000000000006",
    "sr_review": "c3000001-0000-0000-0000-000000000007",
    "sr_reject": "c3000001-0000-0000-0000-000000000008",
    "sr_view": "c3000001-0000-0000-0000-000000000009",
    "cfo_approve": "c3000001-0000-0000-0000-000000000010",
    "cfo_reject": "c3000001-0000-0000-0000-000000000011",
    "cfo_view": "c3000001-0000-0000-0000-000000000012",
    "admin_create": "c3000001-0000-0000-0000-000000000013",
    "admin_submit": "c3000001-0000-0000-0000-000000000014",
    "admin_review": "c3000001-0000-0000-0000-000000000015",
    "admin_approve": "c3000001-0000-0000-0000-000000000016",
    "admin_reject": "c3000001-0000-0000-0000-000000000017",
    "admin_void": "c3000001-0000-0000-0000-000000000018",
    "admin_view": "c3000001-0000-0000-0000-000000000019",
    "admin_export": "c3000001-0000-0000-0000-000000000020",
    "auditor_view": "c3000001-0000-0000-0000-000000000021",
    "auditor_export": "c3000001-0000-0000-0000-000000000022",
}

_SYSTEM_TENANT = "00000000-0000-0000-0000-000000000000"
_HASH_PLACEHOLDER = "0" * 64


def upgrade() -> None:
    op.create_table(
        "accounting_jv_approvals",
        sa.Column("id", UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", UUID(as_uuid=True), nullable=False),
        sa.Column("chain_hash", sa.String(length=64), nullable=True),
        sa.Column("previous_hash", sa.String(length=64), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("jv_id", UUID(as_uuid=True), nullable=False),
        sa.Column("jv_version", sa.Integer(), nullable=False),
        sa.Column("acted_by", UUID(as_uuid=True), nullable=False),
        sa.Column("delegated_from", UUID(as_uuid=True), nullable=True),
        sa.Column("actor_role", sa.String(length=64), nullable=False),
        sa.Column("decision", sa.String(length=16), nullable=False),
        sa.Column("decision_reason", sa.Text(), nullable=True),
        sa.Column("approval_level", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("amount_threshold", sa.Numeric(precision=20, scale=4), nullable=True),
        sa.Column("idempotency_key", sa.String(length=128), nullable=False),
        sa.Column("request_fingerprint", sa.String(length=64), nullable=True),
        sa.Column(
            "acted_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(["jv_id"], ["accounting_jv_aggregates.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["acted_by"], ["iam_users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["delegated_from"], ["iam_users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "tenant_id",
            "jv_id",
            "acted_by",
            "idempotency_key",
            name="uq_jv_approval_idempotency",
        ),
        sa.UniqueConstraint(
            "tenant_id",
            "jv_id",
            "request_fingerprint",
            name="uq_jv_approval_fingerprint",
        ),
    )

    op.create_index("ix_accounting_jv_approvals_jv_id", "accounting_jv_approvals", ["jv_id"])
    op.create_index("ix_accounting_jv_approvals_tenant_id", "accounting_jv_approvals", ["tenant_id"])
    op.create_index("ix_accounting_jv_approvals_acted_by", "accounting_jv_approvals", ["acted_by"])

    op.create_table(
        "approval_sla_timers",
        sa.Column("id", UUID(as_uuid=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("tenant_id", UUID(as_uuid=True), nullable=False),
        sa.Column("jv_id", UUID(as_uuid=True), nullable=False),
        sa.Column("review_sla_hours", sa.Integer(), nullable=False, server_default="24"),
        sa.Column("approval_sla_hours", sa.Integer(), nullable=False, server_default="48"),
        sa.Column("review_breached", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("approval_breached", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("review_breached_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("approval_breached_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("nudge_24h_sent", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("nudge_48h_sent", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(["jv_id"], ["accounting_jv_aggregates.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("jv_id", name="uq_approval_sla_timers_jv_id"),
    )

    op.create_index("ix_approval_sla_timers_tenant_id", "approval_sla_timers", ["tenant_id"])
    op.create_index(
        "ix_approval_sla_timers_breached",
        "approval_sla_timers",
        ["tenant_id", "review_breached", "approval_breached"],
    )

    op.execute("ALTER TABLE accounting_jv_approvals ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE accounting_jv_approvals FORCE ROW LEVEL SECURITY")
    op.execute(
        "CREATE POLICY tenant_isolation ON accounting_jv_approvals "
        "USING (tenant_id = COALESCE(current_setting('app.tenant_id', true), "
        "current_setting('app.current_tenant_id', true))::uuid)"
    )

    op.execute("ALTER TABLE approval_sla_timers ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE approval_sla_timers FORCE ROW LEVEL SECURITY")
    op.execute(
        "CREATE POLICY tenant_isolation ON approval_sla_timers "
        "USING (tenant_id = COALESCE(current_setting('app.tenant_id', true), "
        "current_setting('app.current_tenant_id', true))::uuid)"
    )

    op.execute(append_only_function_sql())
    op.execute(drop_trigger_sql("accounting_jv_approvals"))
    op.execute(create_trigger_sql("accounting_jv_approvals"))

    conn = op.get_bind()

    conn.execute(
        sa.text(
            """
            INSERT INTO cp_roles
                (id, tenant_id, role_code, role_scope, is_active,
                 description, chain_hash, previous_hash, created_at)
            VALUES
                (:id1, :tid, 'ACCOUNTING_PREPARER', 'tenant', true,
                 'Creates and submits Journal Vouchers',
                 :ph, :ph, now()),
                (:id2, :tid, 'ACCOUNTING_REVIEWER', 'tenant', true,
                 'Reviews submitted Journal Vouchers',
                 :ph, :ph, now()),
                (:id3, :tid, 'ACCOUNTING_SR_REVIEWER', 'tenant', true,
                 'Senior reviewer for escalated Journal Vouchers',
                 :ph, :ph, now()),
                (:id4, :tid, 'ACCOUNTING_CFO_APPROVER', 'tenant', true,
                 'Final approver for high-value and escalated JVs',
                 :ph, :ph, now()),
                (:id5, :tid, 'ACCOUNTING_ADMIN', 'tenant', true,
                 'Full accounting administration including void',
                 :ph, :ph, now()),
                (:id6, :tid, 'ACCOUNTING_AUDITOR', 'tenant', true,
                 'Read-only audit access to JV lifecycle',
                 :ph, :ph, now())
            ON CONFLICT (id) DO NOTHING
            """
        ),
        {
            "id1": _R_PREPARER,
            "id2": _R_REVIEWER,
            "id3": _R_SR_REVIEWER,
            "id4": _R_CFO_APPROVER,
            "id5": _R_ACCT_ADMIN,
            "id6": _R_AUDITOR,
            "tid": _SYSTEM_TENANT,
            "ph": _HASH_PLACEHOLDER,
        },
    )

    conn.execute(
        sa.text(
            """
            INSERT INTO cp_permissions
                (id, permission_code, resource_type, action,
                 description, created_at)
            VALUES
                (:p1, 'jv:create', 'JV', 'CREATE', 'Create a Journal Voucher', now()),
                (:p2, 'jv:submit', 'JV', 'SUBMIT', 'Submit a JV for review', now()),
                (:p3, 'jv:review', 'JV', 'REVIEW', 'Mark JV as under review', now()),
                (:p4, 'jv:approve', 'JV', 'APPROVE', 'Approve a JV', now()),
                (:p5, 'jv:reject', 'JV', 'REJECT', 'Reject a JV with reason', now()),
                (:p6, 'jv:void', 'JV', 'VOID', 'Void a JV (admin only)', now()),
                (:p7, 'jv:view', 'JV', 'VIEW', 'View JV details and history', now()),
                (:p8, 'jv:export', 'JV', 'EXPORT', 'Export JV data for audit', now())
            ON CONFLICT (id) DO NOTHING
            """
        ),
        {
            "p1": _P_JV_CREATE,
            "p2": _P_JV_SUBMIT,
            "p3": _P_JV_REVIEW,
            "p4": _P_JV_APPROVE,
            "p5": _P_JV_REJECT,
            "p6": _P_JV_VOID,
            "p7": _P_JV_VIEW,
            "p8": _P_JV_EXPORT,
        },
    )

    rp_rows = [
        (_RP_IDS["preparer_create"], _R_PREPARER, _P_JV_CREATE),
        (_RP_IDS["preparer_submit"], _R_PREPARER, _P_JV_SUBMIT),
        (_RP_IDS["preparer_view"], _R_PREPARER, _P_JV_VIEW),
        (_RP_IDS["reviewer_review"], _R_REVIEWER, _P_JV_REVIEW),
        (_RP_IDS["reviewer_reject"], _R_REVIEWER, _P_JV_REJECT),
        (_RP_IDS["reviewer_view"], _R_REVIEWER, _P_JV_VIEW),
        (_RP_IDS["sr_review"], _R_SR_REVIEWER, _P_JV_REVIEW),
        (_RP_IDS["sr_reject"], _R_SR_REVIEWER, _P_JV_REJECT),
        (_RP_IDS["sr_view"], _R_SR_REVIEWER, _P_JV_VIEW),
        (_RP_IDS["cfo_approve"], _R_CFO_APPROVER, _P_JV_APPROVE),
        (_RP_IDS["cfo_reject"], _R_CFO_APPROVER, _P_JV_REJECT),
        (_RP_IDS["cfo_view"], _R_CFO_APPROVER, _P_JV_VIEW),
        (_RP_IDS["admin_create"], _R_ACCT_ADMIN, _P_JV_CREATE),
        (_RP_IDS["admin_submit"], _R_ACCT_ADMIN, _P_JV_SUBMIT),
        (_RP_IDS["admin_review"], _R_ACCT_ADMIN, _P_JV_REVIEW),
        (_RP_IDS["admin_approve"], _R_ACCT_ADMIN, _P_JV_APPROVE),
        (_RP_IDS["admin_reject"], _R_ACCT_ADMIN, _P_JV_REJECT),
        (_RP_IDS["admin_void"], _R_ACCT_ADMIN, _P_JV_VOID),
        (_RP_IDS["admin_view"], _R_ACCT_ADMIN, _P_JV_VIEW),
        (_RP_IDS["admin_export"], _R_ACCT_ADMIN, _P_JV_EXPORT),
        (_RP_IDS["auditor_view"], _R_AUDITOR, _P_JV_VIEW),
        (_RP_IDS["auditor_export"], _R_AUDITOR, _P_JV_EXPORT),
    ]

    for rp_id, role_id, perm_id in rp_rows:
        conn.execute(
            sa.text(
                """
                INSERT INTO cp_role_permissions
                    (id, tenant_id, role_id, permission_id, effect,
                     chain_hash, previous_hash, created_at)
                VALUES
                    (:id, :tid, :rid, :pid, 'allow',
                     :ph, :ph, now())
                ON CONFLICT (id) DO NOTHING
                """
            ),
            {
                "id": rp_id,
                "tid": _SYSTEM_TENANT,
                "rid": role_id,
                "pid": perm_id,
                "ph": _HASH_PLACEHOLDER,
            },
        )


def downgrade() -> None:
    conn = op.get_bind()

    for rp_id in _RP_IDS.values():
        conn.execute(sa.text("DELETE FROM cp_role_permissions WHERE id = :id"), {"id": rp_id})

    for permission_id in [
        _P_JV_CREATE,
        _P_JV_SUBMIT,
        _P_JV_REVIEW,
        _P_JV_APPROVE,
        _P_JV_REJECT,
        _P_JV_VOID,
        _P_JV_VIEW,
        _P_JV_EXPORT,
    ]:
        conn.execute(sa.text("DELETE FROM cp_permissions WHERE id = :id"), {"id": permission_id})

    for role_id in [
        _R_PREPARER,
        _R_REVIEWER,
        _R_SR_REVIEWER,
        _R_CFO_APPROVER,
        _R_ACCT_ADMIN,
        _R_AUDITOR,
    ]:
        conn.execute(sa.text("DELETE FROM cp_roles WHERE id = :id"), {"id": role_id})

    op.execute(drop_trigger_sql("accounting_jv_approvals"))
    op.execute("DROP POLICY IF EXISTS tenant_isolation ON approval_sla_timers")
    op.execute("DROP POLICY IF EXISTS tenant_isolation ON accounting_jv_approvals")

    op.drop_index("ix_approval_sla_timers_breached", table_name="approval_sla_timers")
    op.drop_index("ix_approval_sla_timers_tenant_id", table_name="approval_sla_timers")
    op.drop_table("approval_sla_timers")

    op.drop_index("ix_accounting_jv_approvals_acted_by", table_name="accounting_jv_approvals")
    op.drop_index("ix_accounting_jv_approvals_tenant_id", table_name="accounting_jv_approvals")
    op.drop_index("ix_accounting_jv_approvals_jv_id", table_name="accounting_jv_approvals")
    op.drop_table("accounting_jv_approvals")
