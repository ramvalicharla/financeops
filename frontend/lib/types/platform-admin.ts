export type PaginatedResponse<T> = {
  data: T[]
  total: number
  limit: number
  offset: number
}

export type PlatformTenantStatus = "active" | "suspended" | "pending"

export type PlatformTenant = {
  id: string
  tenant_id: string
  display_name: string
  slug: string
  tenant_type: string
  country: string
  timezone: string
  status: PlatformTenantStatus
  org_setup_complete: boolean
  org_setup_step: number
  is_platform_tenant: boolean
  created_at: string
  updated_at: string
}

export type PlatformUserRole =
  | "super_admin"
  | "platform_owner"
  | "platform_admin"
  | "platform_support"
  | "finance_leader"
  | "finance_team"
  | "director"
  | "entity_user"
  | "auditor"
  | "hr_manager"
  | "employee"
  | "read_only"

export type PlatformUser = {
  id: string
  tenant_id: string
  email: string
  full_name: string
  role: PlatformUserRole
  is_active: boolean
  mfa_enabled: boolean
  force_mfa_setup: boolean
  created_at: string
}

export type RbacRole = {
  id: string
  tenant_id: string
  role_code: string
  role_scope: string
  inherits_role_id: string | null
  is_active: boolean
  description: string | null
}

export type RbacPermission = {
  id: string
  permission_code: string
  resource_type: string
  action: string
  description: string | null
}

export type RbacRolePermission = {
  id: string
  tenant_id: string
  role_id: string
  permission_id: string
  effect: string
}

export type RbacAssignment = {
  id: string
  tenant_id: string
  user_id: string
  role_id: string
  context_type: string
  context_id: string | null
  is_active: boolean
  effective_from: string
  effective_to: string | null
  assigned_by: string | null
}

export type PlatformFeatureFlag = {
  id: string
  tenant_id: string
  module_id: string
  flag_key: string
  flag_value: Record<string, unknown>
  rollout_mode: "off" | "on" | "canary"
  compute_enabled: boolean
  write_enabled: boolean
  visibility_enabled: boolean
  target_scope_type: "tenant" | "user" | "entity" | "canary"
  target_scope_id: string | null
  traffic_percent: number | null
  effective_from: string
  effective_to: string | null
}
