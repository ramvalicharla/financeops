"""accounting_rbac_seed_and_policy_links

Revision ID: 0101_accounting_rbac_seed_final
Revises: 0100_ap_ageing_audit_export
Create Date: 2026-03-29

Final accounting RBAC seed for Phase 11:
  - upsert six accounting roles
  - add AP ageing / audit export / notification permissions
  - bind new permissions to accounting roles
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0101_accounting_rbac_seed_final"
down_revision: str | None = "0100_ap_ageing_audit_export"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_SYSTEM_TENANT = "00000000-0000-0000-0000-000000000000"
_HASH_PLACEHOLDER = "0" * 64

_R_PREPARER = "a1000001-0000-0000-0000-000000000001"
_R_REVIEWER = "a1000001-0000-0000-0000-000000000002"
_R_SR_REVIEWER = "a1000001-0000-0000-0000-000000000003"
_R_CFO_APPROVER = "a1000001-0000-0000-0000-000000000004"
_R_ACCT_ADMIN = "a1000001-0000-0000-0000-000000000005"
_R_AUDITOR = "a1000001-0000-0000-0000-000000000006"

_P_AP_AGEING_VIEW = "b2000001-0000-0000-0000-000000000009"
_P_AUDIT_EXPORT = "b2000001-0000-0000-0000-000000000010"
_P_NOTIFICATIONS = "b2000001-0000-0000-0000-000000000011"

_RP_NEW: dict[str, str] = {
    "admin_ap_ageing": "c3000001-0000-0000-0000-000000000023",
    "admin_notifications": "c3000001-0000-0000-0000-000000000024",
    "auditor_ap_ageing": "c3000001-0000-0000-0000-000000000025",
    "cfo_ap_ageing": "c3000001-0000-0000-0000-000000000026",
    "reviewer_ap_ageing": "c3000001-0000-0000-0000-000000000027",
    "preparer_notifications": "c3000001-0000-0000-0000-000000000028",
}


def upgrade() -> None:
    conn = op.get_bind()

    conn.execute(
        sa.text(
            """
            INSERT INTO cp_roles
                (id, tenant_id, role_code, role_scope, is_active,
                 description, chain_hash, previous_hash, created_at)
            VALUES
                (:id1, :tid, 'ACCOUNTING_PREPARER',     'ACCOUNTING', true,
                 'Creates and submits Journal Vouchers', :ph, :ph, now()),
                (:id2, :tid, 'ACCOUNTING_REVIEWER',     'ACCOUNTING', true,
                 'Reviews submitted Journal Vouchers', :ph, :ph, now()),
                (:id3, :tid, 'ACCOUNTING_SR_REVIEWER',  'ACCOUNTING', true,
                 'Senior reviewer for escalated JVs', :ph, :ph, now()),
                (:id4, :tid, 'ACCOUNTING_CFO_APPROVER', 'ACCOUNTING', true,
                 'Final approver for high-value JVs', :ph, :ph, now()),
                (:id5, :tid, 'ACCOUNTING_ADMIN',        'ACCOUNTING', true,
                 'Full accounting administration', :ph, :ph, now()),
                (:id6, :tid, 'ACCOUNTING_AUDITOR',      'ACCOUNTING', true,
                 'Read-only audit access', :ph, :ph, now())
            ON CONFLICT ON CONSTRAINT uq_cp_roles_code DO NOTHING
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
                (id, permission_code, resource_type, action, description, created_at)
            VALUES
                (:p9,  'ap_ageing:view',       'AP_AGEING',    'VIEW',
                 'View AP ageing snapshots and reports', now()),
                (:p10, 'audit:export',         'AUDIT',        'EXPORT',
                 'Export audit data (JV lifecycle, push events, approvals)', now()),
                (:p11, 'notification:manage',  'NOTIFICATION', 'MANAGE',
                 'Manage approval notifications and reminders', now())
            ON CONFLICT (permission_code) DO NOTHING
            """
        ),
        {
            "p9": _P_AP_AGEING_VIEW,
            "p10": _P_AUDIT_EXPORT,
            "p11": _P_NOTIFICATIONS,
        },
    )

    new_bindings = [
        (_RP_NEW["admin_ap_ageing"], _R_ACCT_ADMIN, _P_AP_AGEING_VIEW),
        (_RP_NEW["admin_notifications"], _R_ACCT_ADMIN, _P_NOTIFICATIONS),
        (_RP_NEW["auditor_ap_ageing"], _R_AUDITOR, _P_AP_AGEING_VIEW),
        (_RP_NEW["cfo_ap_ageing"], _R_CFO_APPROVER, _P_AP_AGEING_VIEW),
        (_RP_NEW["reviewer_ap_ageing"], _R_REVIEWER, _P_AP_AGEING_VIEW),
        (_RP_NEW["preparer_notifications"], _R_PREPARER, _P_NOTIFICATIONS),
    ]
    for rp_id, role_id, perm_id in new_bindings:
        conn.execute(
            sa.text(
                """
                INSERT INTO cp_role_permissions
                    (id, tenant_id, role_id, permission_id, effect,
                     chain_hash, previous_hash, created_at)
                VALUES
                    (:id, :tid, :rid, :pid, 'ALLOW', :ph, :ph, now())
                ON CONFLICT ON CONSTRAINT uq_cp_role_permission DO NOTHING
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
    for rp_id in _RP_NEW.values():
        conn.execute(
            sa.text("DELETE FROM cp_role_permissions WHERE id = :id"),
            {"id": rp_id},
        )
    for permission_id in (_P_AP_AGEING_VIEW, _P_AUDIT_EXPORT, _P_NOTIFICATIONS):
        conn.execute(
            sa.text("DELETE FROM cp_permissions WHERE id = :id"),
            {"id": permission_id},
        )

