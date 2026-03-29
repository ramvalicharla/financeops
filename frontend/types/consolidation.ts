export interface ConsolidationEntity {
  entity_id: string
  entity_name: string
  currency: string
  fx_rate_to_inr: string
  reporting_period: string
  is_included: boolean
}

export interface EntityBreakdown {
  entity_id: string
  entity_name: string
  currency: string
  fx_rate: string
  revenue_local: string
  revenue_inr: string
  gross_profit_inr: string
  ebitda_inr: string
  net_profit_inr: string
}

export interface ConsolidationSummary {
  period: string
  base_currency: "INR"
  consolidated_revenue: string
  consolidated_gross_profit: string
  consolidated_ebitda: string
  consolidated_net_profit: string
  intercompany_eliminations: string
  fx_translation_difference: string
  entity_breakdown: EntityBreakdown[]
}
