export interface WhiteLabelConfig {
  id: string
  tenant_id: string
  is_enabled: boolean
  custom_domain: string | null
  domain_verified: boolean
  domain_verification_token: string | null
  brand_name: string | null
  logo_url: string | null
  favicon_url: string | null
  primary_colour: string | null
  secondary_colour: string | null
  font_family: string | null
  hide_powered_by: boolean
  custom_css: string | null
  support_email: string | null
  support_url: string | null
  created_at: string
  updated_at: string
}

export interface WhiteLabelAuditLogRow {
  id: string
  tenant_id: string
  changed_by: string
  field_changed: string
  old_value: string | null
  new_value: string | null
  created_at: string
}

export interface PaginatedResult<T> {
  data: T[]
  total: number
  limit: number
  offset: number
}

