export type FDDSeverity = "critical" | "high" | "medium" | "low" | "informational"

export interface FDDEngagement {
  id: string
  tenant_id: string
  engagement_name: string
  target_company_name: string
  analysis_period_start: string
  analysis_period_end: string
  status: "draft" | "running" | "completed" | "failed" | "archived"
  credit_cost: number
  credits_reserved_at: string | null
  credits_deducted_at: string | null
  sections_requested: string[]
  sections_completed: string[]
  created_by: string
  created_at: string
  updated_at: string
}

export interface FDDSection {
  id: string
  engagement_id: string
  tenant_id: string
  section_name: string
  status: "running" | "completed" | "failed"
  result_data: Record<string, unknown>
  ai_narrative: string | null
  computed_at: string
  duration_seconds: string | null
}

export interface FDDFinding {
  id: string
  engagement_id: string
  section_id: string
  tenant_id: string
  finding_type: "risk" | "adjustment" | "normalisation" | "information" | "positive"
  severity: FDDSeverity
  title: string
  description: string
  financial_impact: string | null
  financial_impact_currency: string
  recommended_action: string | null
  created_at: string
}

export interface FDDReport {
  engagement: FDDEngagement
  sections: Record<string, Record<string, unknown>>
  findings: FDDFinding[]
  executive_summary: string
  total_ebitda_adjustments: string
  net_debt: string
  recommended_price_adjustments: string
  ltm_adjusted_ebitda: string
}

export interface PaginatedResult<T> {
  data: T[]
  total: number
  limit: number
  offset: number
}
