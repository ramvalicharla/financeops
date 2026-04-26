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

// ── SP-2A: OrgSwitcher endpoints (/users/me/orgs) ─────────────────────────
// NOTE: See docs/tech-debt/TD-017-user-orgs-endpoint-duplication.md for why
// these are separate from listUserOrgs() above.

export interface UserOrgItem {
  org_id: string
  org_name: string
  org_slug: string
  org_status: string
  role: string
  is_primary: boolean
  joined_at: string
}

export interface UserOrgsListResponse {
  items: UserOrgItem[]
  total: number
}

export interface SwitchOrgTargetOrg {
  id: string
  name: string
  role: string
}

export interface SwitchOrgResponse {
  switch_token: string
  target_org: SwitchOrgTargetOrg
}

export async function listUserSwitchableOrgs(): Promise<UserOrgsListResponse> {
  const res = await apiClient.get<UserOrgsListResponse>("/api/v1/users/me/orgs")
  return res.data
}

export async function switchUserOrg(tenantId: string): Promise<SwitchOrgResponse> {
  const res = await apiClient.post<SwitchOrgResponse>(
    `/api/v1/users/me/orgs/${tenantId}/switch`,
    {},
  )
  return res.data
}
