export type SearchEntityType =
  | "mis_line"
  | "expense_claim"
  | "anomaly"
  | "checklist_task"
  | "fdd_engagement"
  | "ppa_engagement"
  | "ma_workspace"
  | "budget_line"
  | "forecast_run"
  | "marketplace_template"
  | "closing_run"
  | "wc_snapshot"
  | "document"
  | string

export type SearchResultRow = {
  entity_type: SearchEntityType
  entity_id: string
  title: string
  subtitle: string | null
  url: string
  metadata: Record<string, unknown>
  rank: number
}

