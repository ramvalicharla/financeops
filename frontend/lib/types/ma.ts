export interface MAWorkspace {
  id: string
  tenant_id: string
  workspace_name: string
  deal_codename: string
  deal_type: string
  target_company_name: string
  deal_status: string
  indicative_deal_value: string | null
  deal_value_currency: string
  credit_cost_monthly: number
  credit_charged_at: string | null
  created_by: string
  created_at: string
  updated_at: string
}

export interface MAWorkspaceMember {
  id: string
  workspace_id: string
  tenant_id: string
  user_id: string
  member_role: string
  added_at: string
  removed_at: string | null
}

export interface MAValuation {
  id: string
  workspace_id: string
  tenant_id: string
  valuation_name: string
  valuation_method: string
  assumptions: Record<string, string>
  enterprise_value: string
  equity_value: string
  net_debt_used: string
  ev_ebitda_multiple: string
  ev_revenue_multiple: string
  valuation_range_low: string
  valuation_range_high: string
  computed_at: string
  computed_by: string
  notes: string | null
}

export interface MADDItem {
  id: string
  workspace_id: string
  tenant_id: string
  category: string
  item_name: string
  description: string | null
  status: string
  priority: string
  assigned_to: string | null
  due_date: string | null
  response_notes: string | null
  created_at: string
  updated_at: string
}

export interface MADocument {
  id: string
  workspace_id: string
  tenant_id: string
  document_name: string
  document_type: string
  version: number
  file_url: string | null
  file_size_bytes: number | null
  uploaded_by: string
  is_confidential: boolean
  created_at: string
}

export interface MADDTrackerSummary {
  total_items: number
  by_status: Record<string, number>
  by_category: Record<string, number>
  by_priority: Record<string, number>
  completion_pct: string
  flagged_items: MADDItem[]
  overdue_items: MADDItem[]
}

export interface PaginatedResult<T> {
  data: T[]
  total: number
  limit: number
  offset: number
}
