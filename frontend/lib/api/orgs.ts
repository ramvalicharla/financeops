import apiClient from "@/lib/api/client"

export type SubscriptionTier = "starter" | "pro" | "enterprise"

interface UserTenantPayload {
  id: string
  slug: string
  name: string
  role: string
  status: string
  plan: string
}

export interface OrgSummary {
  tenant_id: string
  tenant_slug: string
  display_name: string
  entity_count: number
  last_active_at: string | null
  subscription_tier: SubscriptionTier
  status: string
}

const readSubscriptionTier = (planTier?: string | null): SubscriptionTier => {
  if (planTier === "enterprise") {
    return "enterprise"
  }
  if (planTier === "professional" || planTier === "pro") {
    return "pro"
  }
  return "starter"
}

export const listUserOrgs = async (): Promise<OrgSummary[]> => {
  const response = await apiClient.get<UserTenantPayload[]>("/api/v1/user/tenants")
  return response.data.map((tenant) => ({
    tenant_id: tenant.id,
    tenant_slug: tenant.slug?.trim() || tenant.id,
    display_name: tenant.name,
    entity_count: 0,
    last_active_at: null,
    subscription_tier: readSubscriptionTier(tenant.plan),
    status: tenant.status,
  }))
}
