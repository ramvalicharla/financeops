export interface PPAEngagement {
  id: string
  tenant_id: string
  engagement_name: string
  target_company_name: string
  acquisition_date: string
  purchase_price: string
  purchase_price_currency: string
  accounting_standard: "IFRS3" | "ASC805" | "INDAS103"
  status: "draft" | "running" | "completed" | "failed"
  credit_cost: number
  created_by: string
  created_at: string
  updated_at: string
}

export interface PPAAllocation {
  id: string
  engagement_id: string
  tenant_id: string
  allocation_version: number
  net_identifiable_assets: string
  total_intangibles_identified: string
  goodwill: string
  deferred_tax_liability: string
  purchase_price_reconciliation: Record<string, unknown>
  computed_at: string
}

export interface PPAIntangible {
  id: string
  engagement_id: string
  allocation_id: string
  tenant_id: string
  intangible_name: string
  intangible_category: string
  fair_value: string
  useful_life_years: string
  amortisation_method: string
  annual_amortisation: string
  tax_basis: string
  deferred_tax_liability: string
  valuation_method: string
  valuation_assumptions: Record<string, unknown>
  created_at: string
}

export interface PPAReport {
  engagement: PPAEngagement
  allocation: PPAAllocation
  intangibles: PPAIntangible[]
  purchase_price_bridge: {
    book_value_net_assets: string
    step_ups: Array<{
      name: string
      fair_value: string
      tax_impact: string
    }>
    goodwill: string
    total: string
  }
  amortisation_schedule: Record<string, string>
  goodwill_pct_of_purchase_price: string
}

export interface PPAIntangibleSuggestion {
  intangible_name: string
  intangible_category: string
  rationale: string
  typical_useful_life_years: string
  recommended_valuation_method: string
}

export interface PaginatedResult<T> {
  data: T[]
  total: number
  limit: number
  offset: number
}
