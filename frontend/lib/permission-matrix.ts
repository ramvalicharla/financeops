export type CanonicalRole =
  | "platform_owner"
  | "platform_admin"
  | "tenant_owner"
  | "tenant_admin"
  | "tenant_manager"
  | "tenant_member"
  | "tenant_viewer"

export type PermissionEntry = {
  module: string
  roles: readonly CanonicalRole[]
  entitlement_keys: readonly string[]
  feature_flag: string | null
  runtime_roles: readonly string[]
}

export const ROLE_ALIASES = {
  platform_owner: ["super_admin", "platform_owner"],
  platform_admin: ["platform_admin"],
  tenant_owner: ["finance_leader"],
  tenant_admin: ["finance_leader"],
  tenant_manager: ["director", "hr_manager"],
  tenant_member: [
    "finance_team",
    "employee",
    "entity_user",
    "finance_reviewer",
    "finance_approver",
    "finance_poster",
  ],
  tenant_viewer: ["read_only", "auditor"],
} as const

export const PERMISSIONS = {
  "erp.view": {
    module: "erp",
    roles: ["tenant_member", "tenant_manager", "tenant_admin", "tenant_owner"],
    entitlement_keys: ["erp_integration"],
    feature_flag: null,
    runtime_roles: [],
  },
  "erp.connectors.create": {
    module: "erp",
    roles: ["tenant_admin", "tenant_owner"],
    entitlement_keys: ["erp_integration"],
    feature_flag: null,
    runtime_roles: [],
  },
  "erp.connectors.update": {
    module: "erp",
    roles: ["tenant_admin", "tenant_owner"],
    entitlement_keys: ["erp_integration"],
    feature_flag: null,
    runtime_roles: [],
  },
  "erp.connectors.delete": {
    module: "erp",
    roles: ["tenant_admin", "tenant_owner"],
    entitlement_keys: ["erp_integration"],
    feature_flag: null,
    runtime_roles: [],
  },
  "erp.sync.run": {
    module: "erp",
    roles: ["tenant_admin", "tenant_owner"],
    entitlement_keys: ["erp_integration"],
    feature_flag: null,
    runtime_roles: [],
  },
  "recon.view": {
    module: "reconciliation",
    roles: ["tenant_member", "tenant_manager", "tenant_admin", "tenant_owner"],
    entitlement_keys: [
      "reconciliation",
      "reconciliation_bridge",
      "payroll_gl_reconciliation",
    ],
    feature_flag: null,
    runtime_roles: [],
  },
  "recon.execute": {
    module: "reconciliation",
    roles: ["tenant_admin", "tenant_owner"],
    entitlement_keys: [
      "reconciliation",
      "reconciliation_bridge",
      "payroll_gl_reconciliation",
    ],
    feature_flag: null,
    runtime_roles: [],
  },
  "recon.approve": {
    module: "reconciliation",
    roles: ["tenant_manager", "tenant_admin", "tenant_owner"],
    entitlement_keys: [
      "reconciliation",
      "reconciliation_bridge",
      "payroll_gl_reconciliation",
    ],
    feature_flag: null,
    runtime_roles: [],
  },
  "mis.view": {
    module: "mis",
    roles: ["tenant_member", "tenant_manager", "tenant_admin", "tenant_owner"],
    entitlement_keys: ["mis_manager"],
    feature_flag: null,
    runtime_roles: [],
  },
  "mis.generate": {
    module: "mis",
    roles: ["tenant_manager", "tenant_admin", "tenant_owner"],
    entitlement_keys: ["mis_manager"],
    feature_flag: null,
    runtime_roles: [],
  },
  "workflow.view": {
    module: "workflow",
    roles: ["tenant_member", "tenant_manager", "tenant_admin", "tenant_owner"],
    entitlement_keys: [],
    feature_flag: null,
    runtime_roles: [],
  },
  "workflow.approve": {
    module: "workflow",
    roles: ["tenant_manager", "tenant_admin", "tenant_owner"],
    entitlement_keys: [],
    feature_flag: null,
    runtime_roles: [],
  },
  "workflow.reject": {
    module: "workflow",
    roles: ["tenant_manager", "tenant_admin", "tenant_owner"],
    entitlement_keys: [],
    feature_flag: null,
    runtime_roles: [],
  },
  "close.view": {
    module: "close",
    roles: ["tenant_member", "tenant_manager", "tenant_admin", "tenant_owner"],
    entitlement_keys: [],
    feature_flag: null,
    runtime_roles: [],
  },
  "close.lock": {
    module: "close",
    roles: ["tenant_admin", "tenant_owner"],
    entitlement_keys: [],
    feature_flag: null,
    runtime_roles: ["finance_approver"],
  },
  "close.unlock": {
    module: "close",
    roles: ["tenant_admin", "tenant_owner"],
    entitlement_keys: [],
    feature_flag: null,
    runtime_roles: ["finance_approver"],
  },
  "journal.view": {
    module: "accounting",
    roles: ["tenant_member", "tenant_manager", "tenant_admin", "tenant_owner"],
    entitlement_keys: [],
    feature_flag: null,
    runtime_roles: [],
  },
  "journal.create": {
    module: "accounting",
    roles: ["tenant_member", "tenant_manager", "tenant_admin", "tenant_owner"],
    entitlement_keys: [],
    feature_flag: null,
    runtime_roles: [],
  },
  "journal.submit": {
    module: "accounting",
    roles: ["tenant_member", "tenant_manager", "tenant_admin", "tenant_owner"],
    entitlement_keys: [],
    feature_flag: null,
    runtime_roles: [],
  },
  "journal.review": {
    module: "accounting",
    roles: ["tenant_member", "tenant_admin", "tenant_owner"],
    entitlement_keys: [],
    feature_flag: null,
    runtime_roles: ["finance_reviewer"],
  },
  "journal.approve": {
    module: "accounting",
    roles: ["tenant_admin", "tenant_owner"],
    entitlement_keys: [],
    feature_flag: null,
    runtime_roles: ["finance_approver"],
  },
  "journal.post": {
    module: "accounting",
    roles: ["tenant_admin", "tenant_owner"],
    entitlement_keys: [],
    feature_flag: null,
    runtime_roles: ["finance_poster"],
  },
  "journal.reverse": {
    module: "accounting",
    roles: ["tenant_admin", "tenant_owner"],
    entitlement_keys: [],
    feature_flag: null,
    runtime_roles: ["finance_poster"],
  },
  "audit.access.view": {
    module: "audit",
    roles: ["tenant_member", "tenant_manager", "tenant_admin", "tenant_owner"],
    entitlement_keys: [],
    feature_flag: null,
    runtime_roles: [],
  },
  "audit.access.grant": {
    module: "audit",
    roles: ["tenant_manager", "tenant_admin", "tenant_owner"],
    entitlement_keys: [],
    feature_flag: null,
    runtime_roles: [],
  },
  "audit.access.revoke": {
    module: "audit",
    roles: ["tenant_manager", "tenant_admin", "tenant_owner"],
    entitlement_keys: [],
    feature_flag: null,
    runtime_roles: [],
  },
  "tenant.modules.view": {
    module: "industry_modules",
    roles: ["tenant_member", "tenant_manager", "tenant_admin", "tenant_owner"],
    entitlement_keys: ["industry_modules"],
    feature_flag: null,
    runtime_roles: [],
  },
  "tenant.modules.update": {
    module: "industry_modules",
    roles: ["tenant_admin", "tenant_owner"],
    entitlement_keys: ["industry_modules"],
    feature_flag: null,
    runtime_roles: [],
  },
  "platform.users.view": {
    module: "platform_users",
    roles: ["platform_admin", "platform_owner"],
    entitlement_keys: [],
    feature_flag: null,
    runtime_roles: [],
  },
  "platform.users.create": {
    module: "platform_users",
    roles: ["platform_owner"],
    entitlement_keys: [],
    feature_flag: null,
    runtime_roles: [],
  },
  "platform.users.update": {
    module: "platform_users",
    roles: ["platform_owner"],
    entitlement_keys: [],
    feature_flag: null,
    runtime_roles: [],
  },
  "platform.users.delete": {
    module: "platform_users",
    roles: ["platform_owner"],
    entitlement_keys: [],
    feature_flag: null,
    runtime_roles: [],
  },
  "platform.flags.view": {
    module: "platform_flags",
    roles: ["platform_admin", "platform_owner"],
    entitlement_keys: [],
    feature_flag: null,
    runtime_roles: [],
  },
  "platform.flags.create": {
    module: "platform_flags",
    roles: ["platform_owner"],
    entitlement_keys: [],
    feature_flag: null,
    runtime_roles: [],
  },
  "platform.flags.update": {
    module: "platform_flags",
    roles: ["platform_owner"],
    entitlement_keys: [],
    feature_flag: null,
    runtime_roles: [],
  },
  "platform.flags.delete": {
    module: "platform_flags",
    roles: ["platform_owner"],
    entitlement_keys: [],
    feature_flag: null,
    runtime_roles: [],
  },
  "platform.modules.view": {
    module: "platform_modules",
    roles: ["platform_admin", "platform_owner"],
    entitlement_keys: [],
    feature_flag: null,
    runtime_roles: [],
  },
  "platform.modules.enable": {
    module: "platform_modules",
    roles: ["platform_owner"],
    entitlement_keys: [],
    feature_flag: null,
    runtime_roles: [],
  },
  "platform.modules.update": {
    module: "platform_modules",
    roles: ["platform_owner"],
    entitlement_keys: [],
    feature_flag: null,
    runtime_roles: [],
  },
  "platform.rbac.view": {
    module: "platform_rbac",
    roles: ["platform_admin", "platform_owner"],
    entitlement_keys: [],
    feature_flag: null,
    runtime_roles: [],
  },
  "platform.rbac.manage": {
    module: "platform_rbac",
    roles: ["platform_owner"],
    entitlement_keys: [],
    feature_flag: null,
    runtime_roles: [],
  },
} as const satisfies Record<string, PermissionEntry>

export type PermissionKey = keyof typeof PERMISSIONS

export const ALL_PERMISSIONS = Object.keys(PERMISSIONS).sort() as PermissionKey[]

export const PERMISSIONS_BY_MODULE = Object.entries(PERMISSIONS).reduce<
  Record<string, PermissionKey[]>
>((acc, [permission, entry]) => {
  const key = permission as PermissionKey
  acc[entry.module] ??= []
  acc[entry.module].push(key)
  acc[entry.module].sort()
  return acc
}, {})
