export interface BudgetVersion {
  id: string
  tenant_id: string
  fiscal_year: number
  version_name: string
  version_number: number
  status: "draft" | "submitted" | "approved" | "superseded"
  is_board_approved: boolean
  board_approved_at: string | null
  board_approved_by: string | null
  notes: string | null
  created_by: string
  created_at: string
  updated_at: string
  line_item_count: number | null
}

export interface BudgetLineItem {
  id: string
  budget_version_id: string
  tenant_id: string
  entity_id: string | null
  mis_line_item: string
  mis_category: string
  monthly_values: string[]
  annual_total: string
  basis: string | null
  created_at: string
}

export interface BudgetVsActualMonthly {
  month: string
  budget: string
  actual: string
  variance: string
}

export interface BudgetVsActualLine {
  mis_line_item: string
  mis_category: string
  budget_ytd: string
  actual_ytd: string
  variance_amount: string
  variance_pct: string
  budget_full_year: string
  monthly: BudgetVsActualMonthly[]
}

export interface BudgetVsActualPayload {
  fiscal_year: number
  period_through: string
  version_id: string
  lines: BudgetVsActualLine[]
  summary: {
    total_revenue_budget: string
    total_revenue_actual: string
    ebitda_budget: string
    ebitda_actual: string
    on_budget: boolean
  }
}

export interface PaginatedResult<T> {
  data: T[]
  total: number
  limit: number
  offset: number
}

