export type PaginatedResult<T> = {
  data: T[]
  total: number
  limit: number
  offset: number
}

export type ForecastRun = {
  id: string
  tenant_id: string
  run_name: string
  base_date: string
  weeks: number
  opening_cash_balance: string
  currency: string
  status: "draft" | "published" | "superseded"
  is_published: boolean
  created_by: string
  created_at: string
}

export type ForecastWeek = {
  id: string
  forecast_run_id: string
  week_number: number
  week_start_date: string
  customer_collections: string
  other_inflows: string
  supplier_payments: string
  payroll: string
  rent_and_utilities: string
  loan_repayments: string
  tax_payments: string
  capex: string
  other_outflows: string
  total_inflows: string
  total_outflows: string
  net_cash_flow: string
  closing_balance: string
  notes: string | null
  created_at: string
  updated_at: string
}

export type ForecastSummary = {
  run: ForecastRun
  weeks: ForecastWeek[]
  opening_balance: string
  closing_balance_week_13: string
  minimum_balance: string
  minimum_balance_week: number
  total_inflows: string
  total_outflows: string
  net_position: string
  is_cash_positive: boolean
  weeks_below_zero: number[]
}

export type TaxProvisionRun = {
  id: string
  period: string
  fiscal_year: number
  applicable_tax_rate: string
  accounting_profit_before_tax: string
  permanent_differences: string
  timing_differences: string
  taxable_income: string
  current_tax_expense: string
  deferred_tax_asset: string
  deferred_tax_liability: string
  net_deferred_tax: string
  total_tax_expense: string
  effective_tax_rate: string
  created_by: string
  created_at: string
}

export type TaxPosition = {
  id: string
  tenant_id: string
  position_name: string
  position_type: string
  carrying_amount: string
  tax_base: string
  temporary_difference: string
  deferred_tax_impact: string
  is_asset: boolean
  description: string | null
  created_at: string
  updated_at: string
}

export type TaxSchedule = {
  fiscal_year: number
  periods: TaxProvisionRun[]
  ytd_current_tax: string
  ytd_deferred_tax: string
  ytd_total_tax: string
  effective_tax_rate_ytd: string
  deferred_tax_positions: TaxPosition[]
}

export type CovenantDefinition = {
  id: string
  facility_name: string
  lender_name: string
  covenant_type: string
  covenant_label: string
  threshold_value: string
  threshold_direction: "above" | "below"
  measurement_frequency: string
  is_active: boolean
  grace_period_days: number
  notification_threshold_pct: string
  created_at: string
  updated_at: string
}

export type CovenantEvent = {
  id: string
  covenant_id: string
  tenant_id: string
  period: string
  actual_value: string
  threshold_value: string
  breach_type: "pass" | "near_breach" | "breach"
  variance_pct: string
  computed_at: string
}

export type CovenantDashboardItem = {
  definition: CovenantDefinition
  latest_event: CovenantEvent | null
  trend: "improving" | "stable" | "worsening"
  headroom_pct: string
}

export type CovenantDashboard = {
  total_covenants: number
  passing: number
  near_breach: number
  breached: number
  covenants: CovenantDashboardItem[]
}

export type TransferPricingApplicability = {
  is_required: boolean
  reason: string
  international_transaction_value: string
  domestic_transaction_value: string
}

export type ICTransaction = {
  id: string
  fiscal_year: number
  transaction_type: string
  related_party_name: string
  related_party_country: string
  transaction_amount: string
  currency: string
  transaction_amount_inr: string
  pricing_method: string
  arm_length_price: string | null
  actual_price: string | null
  adjustment_required: string
  is_international: boolean
  description: string | null
  created_at: string
}

export type TransferPricingDoc = {
  id: string
  tenant_id: string
  fiscal_year: number
  document_type: string
  version: number
  content: Record<string, unknown>
  ai_narrative: string | null
  status: string
  filed_at: string | null
  created_by: string
  created_at: string
}

export type SignoffRecord = {
  id: string
  tenant_id: string
  document_type: string
  document_id: string | null
  document_reference: string
  period: string
  signatory_user_id: string
  signatory_name: string
  signatory_role: string
  mfa_verified: boolean
  mfa_verified_at: string | null
  ip_address: string | null
  user_agent: string | null
  declaration_text: string
  content_hash: string
  signature_hash: string
  status: "pending" | "signed" | "revoked"
  signed_at: string | null
  created_at: string
}

export type SignoffCertificatePayload = {
  certificate_number: string
  document_reference: string
  period: string
  signatory_name: string
  signatory_role: string
  signed_at: string | null
  content_hash: string
  signature_hash: string
  is_valid: boolean
  declaration_text: string
}

export type StatutoryCalendarItem = {
  id: string
  form_number: string
  form_description: string
  due_date: string
  filed_date: string | null
  status: "pending" | "filed" | "overdue" | "exempt"
  days_until_due: number
  is_overdue: boolean
}

export type StatutoryFiling = {
  id: string
  form_number: string
  form_description: string
  due_date: string
  filed_date: string | null
  status: "pending" | "filed" | "overdue" | "exempt"
  filing_reference: string | null
  penalty_amount: string | null
  notes: string | null
  created_at: string
}

export type StatutoryRegisterEntry = {
  id: string
  register_type: string
  entry_date: string
  entry_description: string
  folio_number: string | null
  amount: string | null
  currency: string | null
  reference_document: string | null
  is_active: boolean
  created_at: string
  updated_at: string
}

export type GAAPConfig = {
  id: string
  tenant_id: string
  primary_gaap: string
  secondary_gaaps: string[]
  revenue_recognition_policy: Record<string, unknown>
  lease_classification_policy: Record<string, unknown>
  financial_instruments_policy: Record<string, unknown>
  created_at: string
  updated_at: string
}

export type GAAPRun = {
  id: string
  period: string
  gaap_framework: string
  revenue: string
  gross_profit: string
  ebitda: string
  ebit: string
  profit_before_tax: string
  profit_after_tax: string
  total_assets: string
  total_equity: string
  adjustments: Array<Record<string, unknown>>
  created_by: string
  created_at: string
}

export type GAAPComparison = {
  period: string
  frameworks: Array<{
    gaap_framework: string
    revenue: string
    gross_profit: string
    ebitda: string
    profit_before_tax: string
    profit_after_tax: string
    adjustments: Array<Record<string, unknown>>
  }>
  differences: Record<string, Record<string, string>>
}

export type AuditorPortalAccess = {
  id: string
  auditor_email: string
  auditor_firm: string
  engagement_name: string
  access_level: string
  modules_accessible: string[]
  valid_from: string
  valid_until: string
  is_active: boolean
  last_accessed_at: string | null
  created_by: string
  created_at: string
  updated_at: string
}

export type AuditorRequest = {
  id: string
  access_id: string
  request_number: string
  category: string
  description: string
  status: "open" | "in_progress" | "provided" | "partially_provided" | "rejected"
  due_date: string | null
  response_notes: string | null
  evidence_urls: string[]
  provided_at: string | null
  provided_by: string | null
  created_at: string
}

export type PBCTracker = {
  engagement_name: string
  total_requests: number
  open: number
  in_progress: number
  provided: number
  completion_pct: string
  overdue_requests: AuditorRequest[]
  recent_activity: AuditorRequest[]
}
