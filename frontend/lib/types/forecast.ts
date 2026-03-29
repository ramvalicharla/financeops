export interface ForecastRun {
  id: string
  tenant_id: string
  run_name: string
  forecast_type: "rolling_12" | "annual" | "quarterly"
  base_period: string
  horizon_months: number
  status: "draft" | "published" | "superseded"
  is_published: boolean
  published_at: string | null
  published_by: string | null
  created_by: string
  created_at: string
}

export interface ForecastAssumption {
  id: string
  forecast_run_id: string
  tenant_id: string
  assumption_key: string
  assumption_value: string
  assumption_label: string
  category: "growth" | "margins" | "headcount" | "fx" | "capex" | "other"
  basis: string | null
  created_at: string
  updated_at: string
}

export interface ForecastLineItem {
  id: string
  forecast_run_id: string
  tenant_id: string
  period: string
  is_actual: boolean
  mis_line_item: string
  mis_category: string
  amount: string
  entity_id: string | null
  created_at: string
}

export interface ForecastRunDetail {
  run: ForecastRun
  assumptions: ForecastAssumption[]
  line_items: ForecastLineItem[]
}

export interface ForecastVsBudgetRow {
  period: string
  mis_line_item: string
  budget: string
  forecast: string
  variance: string
  variance_pct: string
}

export interface ForecastVsBudgetPayload {
  forecast_run_id: string
  fiscal_year: number
  rows: ForecastVsBudgetRow[]
}

export interface PaginatedResult<T> {
  data: T[]
  total: number
  limit: number
  offset: number
}

