export interface ConsolidationSummaryPayload {
  org_group_id: string
  group_name: string
  as_of_date: string
  from_date: string | null
  to_date: string | null
  reporting_currency: string
  entity_count: number
  elimination_count: number
  total_eliminations: string
  minority_interest_placeholder: string
}

// Legacy dashboard types kept for compatibility with existing components.
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

export interface ConsolidationHierarchyRow {
  org_entity_id: string
  cp_entity_id: string
  legal_name: string
  parent_entity_id: string | null
  ownership_pct: string
  ownership_factor: string
  consolidation_method: string
  weighted_debit: string
  weighted_credit: string
  weighted_balance: string
}

export interface ConsolidationTrialBalanceRow {
  account_code: string
  account_name: string
  debit_sum: string
  credit_sum: string
  balance: string
}

export interface ConsolidationStatementPayload {
  trial_balance: {
    rows: ConsolidationTrialBalanceRow[]
    total_debit: string
    total_credit: string
    is_balanced: boolean
  }
  pnl: Record<string, unknown> | null
  balance_sheet: Record<string, unknown> | null
}

export interface ConsolidationEliminationSummaryRow {
  elimination_type: string
  amount: string
}

export interface ConsolidationSummaryResponse {
  summary: ConsolidationSummaryPayload
  hierarchy: {
    rows: ConsolidationHierarchyRow[]
    root_cp_entity_id: string | null
  }
  statements: ConsolidationStatementPayload
  elimination_summary: ConsolidationEliminationSummaryRow[]
}

export interface ConsolidationRunRequestPayload {
  org_group_id: string
  as_of_date: string
  from_date?: string
  to_date?: string
}

export interface ConsolidationRunAcceptedResponse {
  run_id: string
  workflow_id: string
  status: string
  correlation_id: string
}

export interface ConsolidationRunDetailsResponse {
  run_id: string
  status: string
  event_seq: number
  event_time: string
  workflow_id: string
  configuration: Record<string, unknown>
  summary: ConsolidationSummaryPayload | null
}

export interface ConsolidationRunStatementsResponse {
  run_id: string
  status: string
  statements: ConsolidationStatementPayload
  elimination_summary: ConsolidationEliminationSummaryRow[]
  eliminations: Array<Record<string, unknown>>
  hierarchy: {
    rows: ConsolidationHierarchyRow[]
    root_cp_entity_id: string | null
  } | null
  summary: ConsolidationSummaryPayload | null
}
