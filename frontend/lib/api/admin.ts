import apiClient from "@/lib/api/client"
import type {
  AdminTenantListItem,
  AdminTenantDetail,
  AdminCreditRow,
  AdminPaginatedResponse,
  AdminBillingPlan,
  AdminPlanFormValues,
} from "@/lib/types/admin"

export const adminListTenants = async (params?: {
  limit?: number
  offset?: number
}): Promise<AdminPaginatedResponse<AdminTenantListItem>> => {
  const limit = params?.limit ?? 50
  const offset = params?.offset ?? 0
  const search = new URLSearchParams({
    limit: String(limit),
    offset: String(offset),
  })
  const response = await apiClient.get<unknown>(
    `/api/v1/platform/admin/tenants?${search.toString()}`,
  )
  const payload = response.data as { items?: AdminTenantListItem[]; total?: number } | null
  if (payload && typeof payload === "object" && Array.isArray(payload.items)) {
    return { items: payload.items, total: payload.total ?? payload.items.length, limit, offset }
  }
  if (Array.isArray(payload)) {
    return { items: payload as AdminTenantListItem[], total: (payload as unknown[]).length, limit, offset }
  }
  return { items: [], total: 0, limit, offset }
}

export const adminGetTenant = async (tenantId: string): Promise<AdminTenantDetail> => {
  const response = await apiClient.get<AdminTenantDetail>(
    `/api/v1/platform/admin/tenants/${tenantId}`,
  )
  return response.data
}

export const adminExtendTrial = async (
  tenantId: string,
  days: number,
): Promise<{ success: boolean; new_trial_end_date: string; days_added: number }> => {
  const response = await apiClient.post<{
    success: boolean
    new_trial_end_date: string
    days_added: number
  }>(`/api/v1/platform/admin/tenants/${tenantId}/extend-trial`, { days })
  return response.data
}

export const adminActivateTenant = async (
  tenantId: string,
): Promise<{ success: boolean; subscription_id: string; status: string }> => {
  const response = await apiClient.post<{
    success: boolean
    subscription_id: string
    status: string
  }>(`/api/v1/platform/admin/tenants/${tenantId}/activate`, {})
  return response.data
}

export const adminSuspendTenant = async (
  tenantId: string,
): Promise<{ success: boolean; subscription_id: string; status: string }> => {
  const response = await apiClient.post<{
    success: boolean
    subscription_id: string
    status: string
  }>(`/api/v1/platform/admin/tenants/${tenantId}/suspend`, {})
  return response.data
}

export const adminChangePlan = async (
  tenantId: string,
  planId: string,
): Promise<{ success: boolean; subscription_id: string; plan_id: string; plan_tier: string; credits_allocated: number }> => {
  const response = await apiClient.post<{
    success: boolean
    subscription_id: string
    plan_id: string
    plan_tier: string
    credits_allocated: number
  }>(`/api/v1/platform/admin/tenants/${tenantId}/change-plan`, { plan_id: planId })
  return response.data
}

export const adminSwitchTenant = async (
  tenantId: string,
): Promise<{ switch_token: string; tenant_id: string; tenant_name: string; expires_in_seconds: number }> => {
  const response = await apiClient.post<{
    switch_token: string
    tenant_id: string
    tenant_name: string
    expires_in_seconds: number
  }>(`/api/v1/platform/admin/tenants/${tenantId}/switch`, {})
  return response.data
}

/** Named alias used by OrgSwitcher — calls the same /switch endpoint. */
export const switchToTenant = adminSwitchTenant

// ---------------------------------------------------------------------------
// Plans
// ---------------------------------------------------------------------------

export const adminListPlans = async (): Promise<AdminBillingPlan[]> => {
  const response = await apiClient.get<unknown>("/api/v1/platform/plans")
  const payload = response.data as { items?: AdminBillingPlan[] } | AdminBillingPlan[] | null
  if (Array.isArray(payload)) return payload
  if (payload && typeof payload === "object" && Array.isArray((payload as { items?: AdminBillingPlan[] }).items)) {
    return (payload as { items: AdminBillingPlan[] }).items
  }
  return []
}

export const adminCreatePlan = async (
  values: AdminPlanFormValues,
): Promise<{ id: string; name: string }> => {
  const response = await apiClient.post<{ id: string; name: string }>(
    "/api/v1/platform/plans",
    {
      name: values.name,
      plan_tier: values.plan_tier,
      pricing_type: values.pricing_type,
      price: values.price,
      billing_cycle: values.billing_cycle,
      currency: values.currency,
      included_credits: values.included_credits,
      max_entities: values.max_entities,
      max_connectors: values.max_connectors,
      max_users: values.max_users,
      modules_enabled: values.modules_enabled,
      trial_days: values.trial_days,
      is_active: values.is_active,
      annual_discount_pct: "0",
      entitlements: [],
    },
  )
  return response.data
}

export const adminUpdatePlan = async (
  planId: string,
  values: Partial<AdminPlanFormValues>,
): Promise<{ id: string }> => {
  const response = await apiClient.put<{ id: string }>(
    `/api/v1/platform/plans/${planId}`,
    {
      name: values.name,
      pricing_type: values.pricing_type,
      price: values.price,
      currency: values.currency,
      included_credits: values.included_credits,
      max_entities: values.max_entities,
      max_connectors: values.max_connectors,
      max_users: values.max_users,
      modules_enabled: values.modules_enabled,
      trial_days: values.trial_days,
      is_active: values.is_active,
    },
  )
  return response.data
}

export const adminDeactivatePlan = async (
  planId: string,
): Promise<{ deleted: boolean; replacement_id: string }> => {
  const response = await apiClient.delete<{ deleted: boolean; replacement_id: string }>(
    `/api/v1/platform/plans/${planId}`,
  )
  return response.data
}

// ---------------------------------------------------------------------------
// Credits
// ---------------------------------------------------------------------------

export const adminGrantCredits = async (params: {
  tenant_id: string
  credits: number
  reference_id?: string
}): Promise<{ credit_ledger_id: string; credits_balance_after: number }> => {
  const response = await apiClient.post<{ credit_ledger_id: string; credits_balance_after: number }>(
    "/api/v1/billing/admin/adjust-credits",
    {
      credits: params.credits,
      tenant_id: params.tenant_id,
      reference_id: params.reference_id ?? "platform_admin_grant",
    },
  )
  return response.data
}

export const adminListCredits = async (params?: {
  limit?: number
  offset?: number
  low_balance?: boolean
}): Promise<AdminPaginatedResponse<AdminCreditRow>> => {
  const limit = params?.limit ?? 50
  const offset = params?.offset ?? 0
  const search = new URLSearchParams({ limit: String(limit), offset: String(offset) })
  if (params?.low_balance) search.set("low_balance", "true")
  const response = await apiClient.get<unknown>(
    `/api/v1/platform/admin/credits?${search.toString()}`,
  )
  const payload = response.data as { items?: AdminCreditRow[]; total?: number } | null
  if (payload && typeof payload === "object" && Array.isArray(payload.items)) {
    return { items: payload.items, total: payload.total ?? payload.items.length, limit, offset }
  }
  return { items: [], total: 0, limit, offset }
}
