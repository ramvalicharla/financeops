import apiClient from "@/lib/api/client"
import type {
  PaginatedResponse,
  PlatformFeatureFlag,
  PlatformTenant,
  PlatformTenantStatus,
  PlatformUser,
  PlatformUserRole,
  RbacAssignment,
  RbacPermission,
  RbacRole,
  RbacRolePermission,
} from "@/lib/types/platform-admin"
import type { ServiceRegistryModule } from "@/lib/types/service-registry"

const normalizePaginated = <T>(
  payload: unknown,
  fallbackLimit: number,
  fallbackOffset: number,
): PaginatedResponse<T> => {
  if (Array.isArray(payload)) {
    return {
      data: payload as T[],
      total: payload.length,
      limit: fallbackLimit,
      offset: fallbackOffset,
    }
  }
  const typed = payload as PaginatedResponse<T>
  if (typed && Array.isArray(typed.data)) {
    return typed
  }
  return { data: [], total: 0, limit: fallbackLimit, offset: fallbackOffset }
}

export const listPlatformTenants = async (params?: {
  limit?: number
  offset?: number
  status?: PlatformTenantStatus
}): Promise<PaginatedResponse<PlatformTenant>> => {
  const limit = params?.limit ?? 100
  const offset = params?.offset ?? 0
  const search = new URLSearchParams({
    limit: String(limit),
    offset: String(offset),
  })
  if (params?.status) {
    search.set("status", params.status)
  }
  const response = await apiClient.get<unknown>(`/api/v1/platform/tenants?${search.toString()}`)
  return normalizePaginated<PlatformTenant>(response.data, limit, offset)
}

export const updatePlatformTenantStatus = async (
  tenantId: string,
  status: PlatformTenantStatus,
): Promise<PlatformTenant> => {
  const response = await apiClient.patch<PlatformTenant>(`/api/v1/platform/tenants/${tenantId}/status`, {
    status,
  })
  return response.data
}

export const listPlatformUsers = async (params?: {
  limit?: number
  offset?: number
}): Promise<PaginatedResponse<PlatformUser>> => {
  const limit = params?.limit ?? 100
  const offset = params?.offset ?? 0
  const search = new URLSearchParams({
    limit: String(limit),
    offset: String(offset),
  })
  const response = await apiClient.get<unknown>(`/api/v1/platform/users?${search.toString()}`)
  return normalizePaginated<PlatformUser>(response.data, limit, offset)
}

export const updatePlatformUserRole = async (
  userId: string,
  role: PlatformUserRole,
): Promise<PlatformUser> => {
  const response = await apiClient.patch<PlatformUser>(`/api/v1/platform/users/${userId}/role`, {
    role,
  })
  return response.data
}

export const deactivatePlatformUser = async (userId: string): Promise<PlatformUser> => {
  const response = await apiClient.delete<PlatformUser>(`/api/v1/platform/users/${userId}`)
  return response.data
}

export const listRbacRoles = async (): Promise<RbacRole[]> => {
  const response = await apiClient.get<RbacRole[]>("/api/v1/platform/rbac/roles")
  return response.data
}

export const listRbacPermissions = async (): Promise<RbacPermission[]> => {
  const response = await apiClient.get<RbacPermission[]>("/api/v1/platform/rbac/permissions")
  return response.data
}

export const listRbacRolePermissions = async (): Promise<RbacRolePermission[]> => {
  const response = await apiClient.get<RbacRolePermission[]>("/api/v1/platform/rbac/role-permissions")
  return response.data
}

export const listRbacAssignments = async (): Promise<RbacAssignment[]> => {
  const response = await apiClient.get<RbacAssignment[]>("/api/v1/platform/rbac/assignments")
  return response.data
}

export const createRbacRole = async (payload: {
  role_code: string
  role_scope: string
  is_active?: boolean
  inherits_role_id?: string | null
}): Promise<{ id: string; role_code: string }> => {
  const response = await apiClient.post<{ id: string; role_code: string }>("/api/v1/platform/rbac/roles", payload)
  return response.data
}

export const grantRbacPermission = async (payload: {
  role_id: string
  permission_id: string
  effect: "allow" | "deny"
}): Promise<{ id: string; effect: string }> => {
  const response = await apiClient.post<{ id: string; effect: string }>(
    "/api/v1/platform/rbac/role-permissions",
    payload,
  )
  return response.data
}

export const assignRbacRole = async (payload: {
  user_id: string
  role_id: string
  context_type: string
  context_id?: string | null
  assigned_by?: string | null
  effective_from: string
}): Promise<{ id: string }> => {
  const response = await apiClient.post<{ id: string }>("/api/v1/platform/rbac/assignments", {
    ...payload,
    effective_to: null,
  })
  return response.data
}

export const listFeatureFlags = async (params?: {
  tenant_id?: string
  module_id?: string
}): Promise<PlatformFeatureFlag[]> => {
  const search = new URLSearchParams()
  if (params?.tenant_id) search.set("tenant_id", params.tenant_id)
  if (params?.module_id) search.set("module_id", params.module_id)
  const suffix = search.toString() ? `?${search.toString()}` : ""
  const response = await apiClient.get<PlatformFeatureFlag[]>(`/api/v1/platform/flags${suffix}`)
  return response.data
}

export const createFeatureFlag = async (
  tenantId: string,
  payload: {
    module_id: string
    flag_key: string
    flag_value: Record<string, unknown>
    rollout_mode: "off" | "on" | "canary"
    compute_enabled: boolean
    write_enabled: boolean
    visibility_enabled: boolean
    target_scope_type: "tenant" | "user" | "entity" | "canary"
    target_scope_id?: string | null
    traffic_percent?: number | null
    effective_from: string
    effective_to?: string | null
  },
): Promise<{ id: string; flag_key: string }> => {
  const response = await apiClient.post<{ id: string; flag_key: string }>(
    `/api/v1/platform/flags/tenants/${tenantId}`,
    payload,
  )
  return response.data
}

export const updateFeatureFlag = async (
  flagId: string,
  payload: {
    enabled?: boolean
    rollout_mode?: "off" | "on" | "canary"
    compute_enabled?: boolean
    write_enabled?: boolean
    visibility_enabled?: boolean
    traffic_percent?: number
  },
): Promise<PlatformFeatureFlag> => {
  const response = await apiClient.put<PlatformFeatureFlag>(`/api/v1/platform/flags/${flagId}`, payload)
  return response.data
}

export const deleteFeatureFlag = async (flagId: string): Promise<{ deleted: boolean; id: string }> => {
  const response = await apiClient.delete<{ deleted: boolean; id: string }>(`/api/v1/platform/flags/${flagId}`)
  return response.data
}

export const listPlatformModules = async (): Promise<ServiceRegistryModule[]> => {
  const response = await apiClient.get<unknown>("/api/v1/platform/services/modules?limit=500&offset=0")
  const normalized = normalizePaginated<ServiceRegistryModule>(response.data, 500, 0)
  return normalized.data
}

export const togglePlatformModule = async (
  moduleName: string,
  isEnabled: boolean,
): Promise<ServiceRegistryModule> => {
  const response = await apiClient.patch<ServiceRegistryModule>(
    `/api/v1/platform/services/modules/${moduleName}/toggle`,
    { is_enabled: isEnabled },
  )
  return response.data
}

export const validatePlatformModuleToggle = async (
  moduleName: string,
  payload: {
    is_enabled: boolean
    entity_id?: string | null
  },
): Promise<{
  success: boolean
  failure: boolean
  reason: string | null
  module_name: string
  entity_id: string | null
}> => {
  const response = await apiClient.post<{
    success: boolean
    failure: boolean
    reason: string | null
    module_name: string
    entity_id: string | null
  }>(`/api/v1/platform/services/modules/${moduleName}/toggle/validate`, payload)
  return response.data
}
