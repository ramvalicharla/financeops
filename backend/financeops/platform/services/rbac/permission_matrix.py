from __future__ import annotations

import logging
from collections.abc import Iterable
from typing import Final, TypedDict


logger = logging.getLogger(__name__)


class PermissionEntry(TypedDict):
    module: str
    roles: list[str]
    entitlement_keys: list[str]
    feature_flag: str | None
    runtime_roles: list[str]


PLATFORM_ROLES: Final[tuple[str, ...]] = (
    "platform_owner",
    "platform_admin",
)

TENANT_ROLES: Final[tuple[str, ...]] = (
    "tenant_owner",
    "tenant_admin",
    "tenant_manager",
    "tenant_member",
    "tenant_viewer",
)


ROLE_ALIASES: Final[dict[str, tuple[str, ...]]] = {
    "platform_owner": ("super_admin", "platform_owner"),
    "platform_admin": ("platform_admin",),
    "tenant_owner": ("finance_leader",),
    "tenant_admin": ("finance_leader",),
    "tenant_manager": ("director", "hr_manager"),
    "tenant_member": (
        "finance_team",
        "employee",
        "entity_user",
        "finance_reviewer",
        "finance_approver",
        "finance_poster",
    ),
    "tenant_viewer": ("read_only", "auditor"),
}


PERMISSIONS: Final[dict[str, PermissionEntry]] = {
    "erp.view": {
        "module": "erp",
        "roles": ["tenant_member", "tenant_manager", "tenant_admin", "tenant_owner"],
        "entitlement_keys": ["erp_integration"],
        "feature_flag": None,
        "runtime_roles": [],
    },
    "erp.connectors.create": {
        "module": "erp",
        "roles": ["tenant_admin", "tenant_owner"],
        "entitlement_keys": ["erp_integration"],
        "feature_flag": None,
        "runtime_roles": [],
    },
    "erp.connectors.update": {
        "module": "erp",
        "roles": ["tenant_admin", "tenant_owner"],
        "entitlement_keys": ["erp_integration"],
        "feature_flag": None,
        "runtime_roles": [],
    },
    "erp.connectors.delete": {
        "module": "erp",
        "roles": ["tenant_admin", "tenant_owner"],
        "entitlement_keys": ["erp_integration"],
        "feature_flag": None,
        "runtime_roles": [],
    },
    "erp.sync.run": {
        "module": "erp",
        "roles": ["tenant_admin", "tenant_owner"],
        "entitlement_keys": ["erp_integration"],
        "feature_flag": None,
        "runtime_roles": [],
    },
    "recon.view": {
        "module": "reconciliation",
        "roles": ["tenant_member", "tenant_manager", "tenant_admin", "tenant_owner"],
        "entitlement_keys": [
            "reconciliation",
            "reconciliation_bridge",
            "payroll_gl_reconciliation",
        ],
        "feature_flag": None,
        "runtime_roles": [],
    },
    "recon.execute": {
        "module": "reconciliation",
        "roles": ["tenant_admin", "tenant_owner"],
        "entitlement_keys": [
            "reconciliation",
            "reconciliation_bridge",
            "payroll_gl_reconciliation",
        ],
        "feature_flag": None,
        "runtime_roles": [],
    },
    "recon.approve": {
        "module": "reconciliation",
        "roles": ["tenant_manager", "tenant_admin", "tenant_owner"],
        "entitlement_keys": [
            "reconciliation",
            "reconciliation_bridge",
            "payroll_gl_reconciliation",
        ],
        "feature_flag": None,
        "runtime_roles": [],
    },
    "mis.view": {
        "module": "mis",
        "roles": ["tenant_member", "tenant_manager", "tenant_admin", "tenant_owner"],
        "entitlement_keys": ["mis_manager"],
        "feature_flag": None,
        "runtime_roles": [],
    },
    "mis.generate": {
        "module": "mis",
        "roles": ["tenant_manager", "tenant_admin", "tenant_owner"],
        "entitlement_keys": ["mis_manager"],
        "feature_flag": None,
        "runtime_roles": [],
    },
    "workflow.view": {
        "module": "workflow",
        "roles": ["tenant_member", "tenant_manager", "tenant_admin", "tenant_owner"],
        "entitlement_keys": [],
        "feature_flag": None,
        "runtime_roles": [],
    },
    "workflow.approve": {
        "module": "workflow",
        "roles": ["tenant_manager", "tenant_admin", "tenant_owner"],
        "entitlement_keys": [],
        "feature_flag": None,
        "runtime_roles": [],
    },
    "workflow.reject": {
        "module": "workflow",
        "roles": ["tenant_manager", "tenant_admin", "tenant_owner"],
        "entitlement_keys": [],
        "feature_flag": None,
        "runtime_roles": [],
    },
    "budget.approve": {
        "module": "budgeting",
        "roles": ["tenant_manager", "tenant_admin", "tenant_owner"],
        "entitlement_keys": [],
        "feature_flag": None,
        "runtime_roles": ["finance_leader"],
    },
    "close.view": {
        "module": "close",
        "roles": ["tenant_member", "tenant_manager", "tenant_admin", "tenant_owner"],
        "entitlement_keys": [],
        "feature_flag": None,
        "runtime_roles": [],
    },
    "close.lock": {
        "module": "close",
        "roles": ["tenant_admin", "tenant_owner"],
        "entitlement_keys": [],
        "feature_flag": None,
        "runtime_roles": [
            "finance_approver",
        ],
    },
    "close.unlock": {
        "module": "close",
        "roles": ["tenant_admin", "tenant_owner"],
        "entitlement_keys": [],
        "feature_flag": None,
        "runtime_roles": [
            "finance_approver",
        ],
    },
    "journal.view": {
        "module": "accounting",
        "roles": ["tenant_member", "tenant_manager", "tenant_admin", "tenant_owner"],
        "entitlement_keys": [],
        "feature_flag": None,
        "runtime_roles": [],
    },
    "journal.create": {
        "module": "accounting",
        "roles": ["tenant_member", "tenant_manager", "tenant_admin", "tenant_owner"],
        "entitlement_keys": [],
        "feature_flag": None,
        "runtime_roles": [],
    },
    "journal.submit": {
        "module": "accounting",
        "roles": ["tenant_member", "tenant_manager", "tenant_admin", "tenant_owner"],
        "entitlement_keys": [],
        "feature_flag": None,
        "runtime_roles": [],
    },
    "journal.review": {
        "module": "accounting",
        "roles": [
            "tenant_member",
            "tenant_admin",
            "tenant_owner",
            "platform_admin",
            "platform_owner",
        ],
        "entitlement_keys": [],
        "feature_flag": None,
        "runtime_roles": [
            "finance_reviewer",
        ],
    },
    "journal.approve": {
        "module": "accounting",
        "roles": ["tenant_admin", "tenant_owner", "platform_admin", "platform_owner"],
        "entitlement_keys": [],
        "feature_flag": None,
        "runtime_roles": [
            "finance_approver",
        ],
    },
    "journal.post": {
        "module": "accounting",
        "roles": ["tenant_admin", "tenant_owner", "platform_admin", "platform_owner"],
        "entitlement_keys": [],
        "feature_flag": None,
        "runtime_roles": [
            "finance_poster",
        ],
    },
    "journal.reverse": {
        "module": "accounting",
        "roles": ["tenant_admin", "tenant_owner", "platform_admin", "platform_owner"],
        "entitlement_keys": [],
        "feature_flag": None,
        "runtime_roles": [
            "finance_poster",
        ],
    },
    "audit.access.view": {
        "module": "audit",
        "roles": ["tenant_member", "tenant_manager", "tenant_admin", "tenant_owner"],
        "entitlement_keys": [],
        "feature_flag": None,
        "runtime_roles": [],
    },
    "audit.access.grant": {
        "module": "audit",
        "roles": ["tenant_manager", "tenant_admin", "tenant_owner"],
        "entitlement_keys": [],
        "feature_flag": None,
        "runtime_roles": [],
    },
    "audit.access.revoke": {
        "module": "audit",
        "roles": ["tenant_manager", "tenant_admin", "tenant_owner"],
        "entitlement_keys": [],
        "feature_flag": None,
        "runtime_roles": [],
    },
    "tenant.modules.view": {
        "module": "industry_modules",
        "roles": ["tenant_member", "tenant_manager", "tenant_admin", "tenant_owner"],
        "entitlement_keys": ["industry_modules"],
        "feature_flag": None,
        "runtime_roles": [],
    },
    "tenant.modules.update": {
        "module": "industry_modules",
        "roles": ["tenant_admin", "tenant_owner"],
        "entitlement_keys": ["industry_modules"],
        "feature_flag": None,
        "runtime_roles": [],
    },
    "platform.users.view": {
        "module": "platform_users",
        "roles": ["platform_admin", "platform_owner"],
        "entitlement_keys": [],
        "feature_flag": None,
        "runtime_roles": [],
    },
    "platform.users.create": {
        "module": "platform_users",
        "roles": ["platform_owner"],
        "entitlement_keys": [],
        "feature_flag": None,
        "runtime_roles": [],
    },
    "platform.users.update": {
        "module": "platform_users",
        "roles": ["platform_owner"],
        "entitlement_keys": [],
        "feature_flag": None,
        "runtime_roles": [],
    },
    "platform.users.delete": {
        "module": "platform_users",
        "roles": ["platform_owner"],
        "entitlement_keys": [],
        "feature_flag": None,
        "runtime_roles": [],
    },
    "platform.flags.view": {
        "module": "platform_flags",
        "roles": ["platform_admin", "platform_owner"],
        "entitlement_keys": [],
        "feature_flag": None,
        "runtime_roles": [],
    },
    "platform.flags.create": {
        "module": "platform_flags",
        "roles": ["platform_owner"],
        "entitlement_keys": [],
        "feature_flag": None,
        "runtime_roles": [],
    },
    "platform.flags.update": {
        "module": "platform_flags",
        "roles": ["platform_owner"],
        "entitlement_keys": [],
        "feature_flag": None,
        "runtime_roles": [],
    },
    "platform.flags.delete": {
        "module": "platform_flags",
        "roles": ["platform_owner"],
        "entitlement_keys": [],
        "feature_flag": None,
        "runtime_roles": [],
    },
    "platform.modules.view": {
        "module": "platform_modules",
        "roles": ["platform_admin", "platform_owner"],
        "entitlement_keys": [],
        "feature_flag": None,
        "runtime_roles": [],
    },
    "platform.modules.enable": {
        "module": "platform_modules",
        "roles": ["platform_owner"],
        "entitlement_keys": [],
        "feature_flag": None,
        "runtime_roles": [],
    },
    "platform.modules.update": {
        "module": "platform_modules",
        "roles": ["platform_owner"],
        "entitlement_keys": [],
        "feature_flag": None,
        "runtime_roles": [],
    },
    "platform.rbac.view": {
        "module": "platform_rbac",
        "roles": ["platform_admin", "platform_owner"],
        "entitlement_keys": [],
        "feature_flag": None,
        "runtime_roles": [],
    },
    "platform.rbac.manage": {
        "module": "platform_rbac",
        "roles": ["platform_owner"],
        "entitlement_keys": [],
        "feature_flag": None,
        "runtime_roles": [],
    },
}


PERMISSIONS_BY_MODULE: Final[dict[str, list[str]]] = {}
for permission_name, entry in PERMISSIONS.items():
    PERMISSIONS_BY_MODULE.setdefault(entry["module"], []).append(permission_name)

for module_permissions in PERMISSIONS_BY_MODULE.values():
    module_permissions.sort()


def validate_permission_matrix(
    entries: Iterable[tuple[str, PermissionEntry]] | None = None,
) -> None:
    seen_keys: set[str] = set()
    source = PERMISSIONS.items() if entries is None else entries
    count = 0
    for key, value in source:
        if key in seen_keys:
            raise ValueError(f"Duplicate permission key: {key}")
        if value is None:
            raise ValueError(f"Permission key has None value: {key}")
        seen_keys.add(key)
        count += 1
    logger.info("Permission matrix validated: %s permissions OK", count)
