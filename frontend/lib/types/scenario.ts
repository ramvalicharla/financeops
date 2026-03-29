export interface ScenarioSet {
  id: string
  tenant_id: string
  name: string
  base_period: string
  horizon_months: number
  base_forecast_run_id: string | null
  created_by: string
  created_at: string
}

export interface ScenarioDefinition {
  id: string
  scenario_set_id: string
  tenant_id: string
  scenario_name: "base" | "optimistic" | "pessimistic" | "custom"
  scenario_label: string
  is_base_case: boolean
  driver_overrides: Record<string, string>
  colour_hex: string
  created_at: string
  updated_at: string
}

export interface ScenarioResultSummary {
  id: string
  scenario_definition_id: string
  line_items_count: number
  computed_at: string
}

export interface ScenarioComparisonScenario {
  scenario_name: string
  scenario_label: string
  colour_hex: string
  is_base_case: boolean
  summary: {
    revenue_total: string
    ebitda_total: string
    ebitda_margin_pct: string
    net_profit_total: string
  }
  monthly: Array<{
    period: string
    revenue: string
    ebitda: string
  }>
}

export interface ScenarioComparisonPayload {
  scenario_set_name: string
  base_period: string
  scenarios: ScenarioComparisonScenario[]
  waterfall: {
    base_ebitda: string
    drivers: Array<{
      driver_name: string
      impact: string
    }>
    optimistic_ebitda: string
    pessimistic_ebitda: string
  }
}

export interface PaginatedResult<T> {
  data: T[]
  total: number
  limit: number
  offset: number
}

