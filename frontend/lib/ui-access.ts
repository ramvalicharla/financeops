import type { UserRole } from "@/lib/auth"
import type {
  NavigationGroupItem,
  NavigationItem,
  NavigationLeafItem,
} from "@/lib/config/navigation"
import { PERMISSIONS, ROLE_ALIASES } from "./permission-matrix"
import type { BillingEntitlement } from "@/types/billing"

type KnownUserRole =
  | UserRole
  | string
  | null
  | undefined

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

const resolveCanonicalRoles = (role: KnownUserRole): Set<string> => {
  const normalizedRole = normalize(String(role ?? ""))
  const resolved = new Set<string>()
  for (const [canonicalRole, aliases] of Object.entries(ROLE_ALIASES)) {
    if (aliases.some((alias) => normalize(alias) === normalizedRole)) {
      resolved.add(canonicalRole)
    }
  }
  return resolved
}

export const isPlatformOwner = (role: KnownUserRole): boolean =>
  resolveCanonicalRoles(role).has("platform_owner")

export const isPlatformAdmin = (role: KnownUserRole): boolean =>
  resolveCanonicalRoles(role).has("platform_admin") || isPlatformOwner(role)

export const isTenantAdmin = (role: KnownUserRole): boolean =>
  resolveCanonicalRoles(role).has("tenant_admin") || resolveCanonicalRoles(role).has("tenant_owner")

export const isTenantManager = (role: KnownUserRole): boolean =>
  resolveCanonicalRoles(role).has("tenant_manager") || isTenantAdmin(role)

export const isTenantViewer = (role: KnownUserRole): boolean =>
  resolveCanonicalRoles(role).has("tenant_viewer")

type ActionAccessContext = {
  role: KnownUserRole
  entitlements?: BillingEntitlement[]
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
  const entry = PERMISSIONS[permission as keyof typeof PERMISSIONS]
  if (!entry) {
    return false
  }

  const context = normalizeActionContext(roleOrContext)
  const runtimeRole = normalize(String(context.role ?? ""))
  const canonicalRoles = resolveCanonicalRoles(context.role)
  const roleAllowed =
    entry.runtime_roles.some((allowedRole) => normalize(allowedRole) === runtimeRole) ||
    entry.roles.some((allowedRole) => canonicalRoles.has(allowedRole))

  if (!roleAllowed) {
    return false
  }

  if (!entry.entitlement_keys.length) {
    return true
  }

  return hasEntitlement(context.entitlements, entry.entitlement_keys)
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
