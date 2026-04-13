import apiClient from "@/lib/api/client"

export type SubscriptionTier = "starter" | "pro" | "enterprise"

export interface OrgSummary {
  tenant_id: string
  tenant_slug: string
  display_name: string
  entity_count: number
  last_active_at: string | null
  subscription_tier: SubscriptionTier
  status: string
}

export const listUserOrgs = async (): Promise<OrgSummary[]> => {
  const response = await apiClient.get<OrgSummary[]>("/api/v1/user/tenants")
  return response.data
}
