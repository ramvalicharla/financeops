export interface ApiResponse<T> {
  data: T | null
  error: {
    code: string
    message: string
    details?: unknown
  } | null
  meta: {
    request_id: string
    timestamp: string
  }
}

export interface EntityRole {
  entity_id: string
  entity_name: string
  role: "admin" | "accountant" | "auditor" | "viewer"
}

export type CoaStatus = "pending" | "uploaded" | "skipped" | "erp_connected"

export interface User {
  id: string
  email: string
  name: string
  tenant_id: string
  tenant_slug: string
  org_setup_complete: boolean
  org_setup_step: number
  coa_status: CoaStatus
  onboarding_score: number
  entity_roles: EntityRole[]
}

export interface TenantProfile {
  tenant_id: string
  display_name: string
  tenant_type: string
  country: string
  timezone: string
  pan?: string | null
  gstin?: string | null
  state_code?: string | null
  status: string
  org_setup_complete: boolean
  org_setup_step: number
  coa_status: CoaStatus
  onboarding_score: number
  created_at: string
}
