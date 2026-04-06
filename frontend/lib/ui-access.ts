import type { UserRole } from "@/lib/auth"
import type {
  NavigationGroupItem,
  NavigationItem,
  NavigationLeafItem,
} from "@/lib/config/navigation"
import type { BillingEntitlement } from "@/types/billing"

type KnownUserRole =
  | UserRole
  | string
  | null
  | undefined

const PLATFORM_OWNER_ROLES = new Set<KnownUserRole>([
  "super_admin",
  "platform_owner",
])

const PLATFORM_ADMIN_ROLES = new Set<KnownUserRole>([
  "super_admin",
  "platform_owner",
  "platform_admin",
])

const TENANT_ADMIN_ROLES = new Set<KnownUserRole>([
  "super_admin",
  "platform_owner",
  "platform_admin",
  "finance_leader",
])

const TENANT_MANAGER_ROLES = new Set<KnownUserRole>([
  "super_admin",
  "platform_owner",
  "platform_admin",
  "finance_leader",
  "director",
  "hr_manager",
])

const ROUTE_FEATURES: Record<string, readonly string[]> = {
  "/dashboard/cfo": ["analytics"],
  "/dashboard/kpis": ["analytics"],
  "/dashboard/variance": ["analytics", "ratio_variance_engine"],
  "/dashboard/trends": ["analytics"],
  "/dashboard/ratios": ["analytics", "ratio_variance_engine"],
  "/ai/dashboard": ["ai_cfo"],
  "/ai/anomalies": ["anomaly_pattern_engine", "ai_cfo"],
  "/ai/recommendations": ["ai_cfo"],
  "/ai/narrative": ["board_pack_narrative_engine", "ai_cfo"],
  "/sync": ["erp_integration"],
  "/erp/connectors": ["erp_integration"],
  "/erp/sync": ["erp_integration"],
  "/erp/mappings": ["erp_integration"],
  "/reconciliation/gl-tb": ["reconciliation_bridge", "reconciliation"],
  "/reconciliation/payroll": ["payroll_gl_reconciliation", "reconciliation"],
  "/mis": ["mis_manager"],
  "/consolidation": ["multi_entity_consolidation", "consolidation"],
  "/consolidation/translation": [
    "fx_translation_reporting",
    "multi_entity_consolidation",
    "consolidation",
  ],
  "/board-pack": ["board_pack_narrative_engine"],
  "/anomalies": ["anomaly_pattern_engine"],
  "/treasury": ["cash_flow_engine"],
  "/modules": ["industry_modules"],
  "/modules/lease": ["lease"],
  "/modules/revenue": ["revenue"],
  "/modules/assets": ["fixed_assets", "assets"],
  "/modules/prepaid": ["prepaid"],
  "/fixed-assets": ["fixed_assets", "assets"],
  "/prepaid": ["prepaid"],
  "/tax": ["gst"],
  "/covenants": ["financial_risk_engine"],
  "/gaap": ["fx_translation_reporting"],
}

const MANAGEMENT_SETTINGS = new Set<string>(["/settings/users", "/settings/groups"])

const ENTITLEMENT_ERROR_CODES = new Set<string>([
  "entitlement_not_configured",
  "ENTITLEMENT_NOT_CONFIGURED",
])

const normalize = (value: string): string => value.trim().toLowerCase()

export const isPlatformOwner = (role: KnownUserRole): boolean =>
  PLATFORM_OWNER_ROLES.has(role)

export const isPlatformAdmin = (role: KnownUserRole): boolean =>
  PLATFORM_ADMIN_ROLES.has(role)

export const isTenantAdmin = (role: KnownUserRole): boolean =>
  TENANT_ADMIN_ROLES.has(role)

export const isTenantManager = (role: KnownUserRole): boolean =>
  TENANT_MANAGER_ROLES.has(role)

const TENANT_MEMBER_ROLES = new Set<KnownUserRole>([
  "super_admin",
  "platform_owner",
  "platform_admin",
  "finance_leader",
  "finance_team",
  "director",
  "hr_manager",
  "employee",
  "entity_user",
  "finance_reviewer",
  "finance_approver",
  "finance_poster",
])

type PermissionRule = {
  featureKeys?: readonly string[]
  allows: (role: KnownUserRole) => boolean
}

type ActionAccessContext = {
  role: KnownUserRole
  entitlements?: BillingEntitlement[]
}

const allowsTenantMember = (role: KnownUserRole): boolean =>
  TENANT_MEMBER_ROLES.has(role)

const allowsJournalReview = (role: KnownUserRole): boolean =>
  [
    "finance_reviewer",
    "finance_team",
    "finance_leader",
    "super_admin",
    "platform_owner",
    "platform_admin",
  ].includes(String(role))

const allowsJournalApproval = (role: KnownUserRole): boolean =>
  [
    "finance_approver",
    "finance_leader",
    "super_admin",
    "platform_owner",
    "platform_admin",
  ].includes(String(role))

const allowsJournalPosting = (role: KnownUserRole): boolean =>
  [
    "finance_poster",
    "finance_leader",
    "super_admin",
    "platform_owner",
    "platform_admin",
  ].includes(String(role))

const PERMISSION_RULES: Record<string, PermissionRule> = {
  "erp.connectors.create": {
    featureKeys: ["erp_integration"],
    allows: isTenantAdmin,
  },
  "erp.connectors.update": {
    featureKeys: ["erp_integration"],
    allows: isTenantAdmin,
  },
  "erp.connectors.delete": {
    featureKeys: ["erp_integration"],
    allows: isTenantAdmin,
  },
  "erp.sync.run": {
    featureKeys: ["erp_integration"],
    allows: isTenantAdmin,
  },
  "recon.execute": {
    featureKeys: ["reconciliation", "reconciliation_bridge", "payroll_gl_reconciliation"],
    allows: isTenantAdmin,
  },
  "recon.approve": {
    featureKeys: ["reconciliation", "reconciliation_bridge", "payroll_gl_reconciliation"],
    allows: isTenantManager,
  },
  "mis.generate": {
    featureKeys: ["mis_manager"],
    allows: isTenantManager,
  },
  "workflow.approve": {
    allows: isTenantManager,
  },
  "workflow.reject": {
    allows: isTenantManager,
  },
  "close.lock": {
    allows: allowsJournalApproval,
  },
  "close.unlock": {
    allows: allowsJournalApproval,
  },
  "journal.create": {
    allows: allowsTenantMember,
  },
  "journal.submit": {
    allows: allowsTenantMember,
  },
  "journal.review": {
    allows: allowsJournalReview,
  },
  "journal.approve": {
    allows: allowsJournalApproval,
  },
  "journal.post": {
    allows: allowsJournalPosting,
  },
  "journal.reverse": {
    allows: allowsJournalPosting,
  },
  "platform.users.create": {
    allows: isPlatformOwner,
  },
  "platform.users.update": {
    allows: isPlatformOwner,
  },
  "platform.users.delete": {
    allows: isPlatformOwner,
  },
  "platform.flags.create": {
    allows: isPlatformOwner,
  },
  "platform.flags.update": {
    allows: isPlatformOwner,
  },
  "platform.flags.delete": {
    allows: isPlatformOwner,
  },
  "platform.modules.enable": {
    allows: isPlatformOwner,
  },
  "platform.modules.update": {
    allows: isPlatformOwner,
  },
  "platform.rbac.manage": {
    allows: isPlatformOwner,
  },
  "tenant.modules.update": {
    featureKeys: ["industry_modules"],
    allows: isTenantAdmin,
  },
  "audit.access.grant": {
    allows: isTenantManager,
  },
  "audit.access.revoke": {
    allows: isTenantManager,
  },
}

const normalizeActionContext = (
  roleOrContext: KnownUserRole | ActionAccessContext,
): ActionAccessContext =>
  roleOrContext && typeof roleOrContext === "object" && "role" in roleOrContext
    ? roleOrContext
    : { role: roleOrContext as KnownUserRole }

export const canPerformAction = (
  permission: string,
  roleOrContext: KnownUserRole | ActionAccessContext,
): boolean => {
  const rule = PERMISSION_RULES[permission]
  if (!rule) {
    return false
  }

  const context = normalizeActionContext(roleOrContext)
  if (!rule.allows(context.role)) {
    return false
  }

  if (!rule.featureKeys?.length) {
    return true
  }

  return hasEntitlement(context.entitlements, rule.featureKeys)
}

export const getPermissionDeniedMessage = (permission: string): string => {
  if (permission.startsWith("platform.")) {
    return "You do not have permission."
  }
  if (permission.startsWith("erp.") || permission.startsWith("tenant.")) {
    return "You do not have permission."
  }
  if (permission.startsWith("journal.") || permission.startsWith("close.")) {
    return "You do not have permission."
  }
  if (permission.startsWith("workflow.")) {
    return "You do not have permission."
  }
  return "You do not have permission."
}

export const hasEntitlement = (
  entitlements: BillingEntitlement[] | undefined,
  featureKeys: readonly string[],
): boolean => {
  if (!featureKeys.length) {
    return true
  }
  const available = new Set(
    (entitlements ?? []).map((entitlement) => normalize(entitlement.feature_name)),
  )
  return featureKeys.some((featureKey) => available.has(normalize(featureKey)))
}

export const canAccessModule = (
  moduleKey: string | readonly string[],
  entitlements: BillingEntitlement[] | undefined,
): boolean => {
  const featureKeys = Array.isArray(moduleKey) ? moduleKey : [moduleKey]
  return hasEntitlement(entitlements, featureKeys)
}

const canAccessNavigationHref = (
  href: string,
  role: KnownUserRole,
  entitlements: BillingEntitlement[] | undefined,
  entitlementsLoaded: boolean,
): boolean => {
  if (MANAGEMENT_SETTINGS.has(href) && !isTenantAdmin(role)) {
    return false
  }
  if (href === "/settings/white-label" && !isTenantAdmin(role)) {
    return false
  }

  const featureKeys = ROUTE_FEATURES[href]
  if (!featureKeys) {
    return true
  }

  if (!entitlementsLoaded) {
    return false
  }

  return hasEntitlement(entitlements, featureKeys)
}

export const filterNavigationItems = (
  items: readonly NavigationItem[],
  role: KnownUserRole,
  entitlements: BillingEntitlement[] | undefined,
  entitlementsLoaded: boolean,
): NavigationItem[] =>
  items.reduce<NavigationItem[]>((visibleItems, item) => {
    if ("children" in item) {
      const children = item.children.filter((child) =>
        canAccessNavigationHref(child.href, role, entitlements, entitlementsLoaded),
      )
      if (children.length) {
        visibleItems.push({ ...item, children } satisfies NavigationGroupItem)
      }
      return visibleItems
    }

    if (
      canAccessNavigationHref(
      item.href,
      role,
      entitlements,
      entitlementsLoaded,
    )
    ) {
      visibleItems.push(item satisfies NavigationLeafItem)
    }
    return visibleItems
  }, [])

const getErrorCode = (error: unknown): string | null => {
  if (!error || typeof error !== "object") {
    return null
  }
  const candidate = error as {
    payload?: { code?: unknown }
    code?: unknown
  }
  if (typeof candidate.payload?.code === "string") {
    return candidate.payload.code
  }
  if (typeof candidate.code === "string") {
    return candidate.code
  }
  return null
}

const getErrorMessage = (error: unknown): string | null => {
  if (typeof error === "string") {
    return error
  }
  if (!error || typeof error !== "object") {
    return null
  }
  const candidate = error as {
    payload?: { message?: unknown }
    message?: unknown
  }
  if (typeof candidate.payload?.message === "string") {
    return candidate.payload.message
  }
  if (typeof candidate.message === "string") {
    return candidate.message
  }
  return null
}

const getErrorStatus = (error: unknown): number | null => {
  if (!error || typeof error !== "object") {
    return null
  }
  const candidate = error as {
    response?: { status?: unknown }
  }
  return typeof candidate.response?.status === "number"
    ? candidate.response.status
    : null
}

export const isEntitlementError = (error: unknown): boolean => {
  const code = getErrorCode(error)
  if (code && ENTITLEMENT_ERROR_CODES.has(code)) {
    return true
  }

  const message = getErrorMessage(error)
  if (!message) {
    return false
  }

  const normalized = normalize(message)
  return (
    normalized.includes("entitlement_not_configured") ||
    normalized.includes("module not enabled") ||
    normalized.includes("not enabled for your organization")
  )
}

export const getModuleDisabledMessage = (moduleLabel?: string): string =>
  moduleLabel
    ? `${moduleLabel} is not enabled for your organization.`
    : "Module not enabled for your organization."

export const getAccessErrorMessage = (
  error: unknown,
  moduleLabel?: string,
): string | null => {
  if (!error) {
    return null
  }
  if (isEntitlementError(error)) {
    return getModuleDisabledMessage(moduleLabel)
  }

  const status = getErrorStatus(error)
  const message = getErrorMessage(error)
  if (
    status === 403 ||
    (message && normalize(message).includes("permission denied"))
  ) {
    return "You do not have access to this action."
  }

  return null
}
