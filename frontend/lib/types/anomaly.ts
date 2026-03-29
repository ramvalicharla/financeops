export type AnomalySeverity = "LOW" | "MEDIUM" | "HIGH" | "CRITICAL" | "INFO"

export type AnomalyStatus = "OPEN" | "SNOOZED" | "RESOLVED" | "ESCALATED"

export interface AnomalyAlert {
  id: string
  tenant_id: string
  alert_type: string
  rule_code: string
  severity: string
  category: string
  detected_at: string
  alert_status: AnomalyStatus
  snoozed_until: string | null
  resolved_at: string | null
  escalated_at: string | null
  status_note: string | null
  status_updated_by: string | null
  run_id: string
  line_no: number
  anomaly_code: string
  anomaly_name: string
  anomaly_score: string
  confidence_score: string
  persistence_classification: string
  correlation_flag: boolean
  materiality_elevated: boolean
  risk_elevated: boolean
  board_flag: boolean
  source_summary_json: Record<string, unknown>
  source_table: string | null
  source_row_id: string | null
  created_by: string
  created_at: string
}

export interface UpdateAnomalyStatusRequest {
  status: Exclude<AnomalyStatus, "OPEN">
  snoozed_until?: string
  note?: string
}

export interface AnomalyThreshold {
  rule_code: string
  current_threshold: string
  config: Record<string, unknown>
  status: string
  effective_from: string
}

export interface UpdateAnomalyThresholdRequest {
  threshold_value: string
  config: Record<string, unknown>
}

export interface UpdateAnomalyThresholdResponse {
  rule_code: string
  updated: boolean
}
