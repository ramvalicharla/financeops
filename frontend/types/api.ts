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

export interface User {
  id: string
  email: string
  name: string
  tenant_id: string
  tenant_slug: string
  org_setup_complete: boolean
  org_setup_step: number
  entity_roles: EntityRole[]
}
