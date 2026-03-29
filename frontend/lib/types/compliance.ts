export type RAGStatus = "green" | "amber" | "red" | "grey"

export type ComplianceControl = {
  id?: string
  control_id: string
  control_name: string
  control_description?: string | null
  category: string
  status: "not_evaluated" | "pass" | "fail" | "partial" | "not_applicable"
  rag_status: RAGStatus
  auto_evaluable: boolean
  last_evaluated_at?: string | null
  next_evaluation_due?: string | null
  evidence_summary?: string | null
}

export type ComplianceSummary = {
  green: number
  amber: number
  red: number
  grey: number
  total: number
}

export type ComplianceDashboard = {
  overall_rag: RAGStatus
  last_evaluated: string | null
  summary: ComplianceSummary
  controls_by_category: Record<string, ComplianceControl[]>
  recently_failed: Array<Record<string, unknown>>
  upcoming_evaluations: Array<Record<string, unknown>>
}

export type ConsentCoverageRow = {
  consent_type: string
  granted_count: number
  withdrawn_count: number
  coverage_pct: string
}

export type ConsentSummary = {
  total_users: number
  consent: ConsentCoverageRow[]
}

export type GDPRBreach = {
  id: string
  breach_type: string
  description: string
  affected_user_count: number
  affected_data_types: string[]
  discovered_at: string
  reported_to_dpa_at: string | null
  notified_users_at: string | null
  severity: "low" | "medium" | "high" | "critical"
  status: "open" | "reported" | "closed"
  remediation_notes: string | null
  created_at: string
}
