export enum ReportRunStatus {
  PENDING = "PENDING",
  RUNNING = "RUNNING",
  COMPLETE = "COMPLETE",
  FAILED = "FAILED",
}

export enum ReportExportFormat {
  CSV = "CSV",
  EXCEL = "EXCEL",
  PDF = "PDF",
}

export enum FilterOperator {
  EQ = "EQ",
  NEQ = "NEQ",
  GT = "GT",
  GTE = "GTE",
  LT = "LT",
  LTE = "LTE",
  IN = "IN",
  BETWEEN = "BETWEEN",
}

export enum SortDirection {
  ASC = "ASC",
  DESC = "DESC",
}

export interface MetricDefinition {
  key: string
  label: string
  source_table: string
  source_column: string
  data_type: string
  engine: string
}

export interface FilterCondition {
  field: string
  operator: FilterOperator
  value: unknown
}

export interface FilterConfig {
  conditions: FilterCondition[]
  period_start: string | null
  period_end: string | null
  entity_ids: string[]
  account_codes: string[]
  tags: string[]
  amount_min: string | null
  amount_max: string | null
}

export interface SortConfig {
  field: string
  direction: SortDirection
}

export interface ReportDefinitionResponse {
  id: string
  tenant_id: string
  name: string
  description: string | null
  metric_keys: string[]
  filter_config: FilterConfig
  group_by: string[]
  sort_config: SortConfig | Record<string, never>
  export_formats: ReportExportFormat[]
  config: Record<string, unknown>
  created_by: string
  created_at: string
  updated_at: string
  is_active: boolean
}

export interface CreateReportDefinitionRequest {
  name: string
  description?: string | null
  metric_keys: string[]
  filter_config: FilterConfig
  group_by?: string[]
  sort_config?: SortConfig
  export_formats?: ReportExportFormat[]
  config?: Record<string, unknown>
}

export interface UpdateReportDefinitionRequest {
  name?: string
  description?: string | null
  metric_keys?: string[]
  filter_config?: FilterConfig
  group_by?: string[]
  sort_config?: SortConfig
  export_formats?: ReportExportFormat[]
  config?: Record<string, unknown>
}

export interface ReportRunResponse {
  id: string
  tenant_id: string
  definition_id: string
  status: ReportRunStatus
  triggered_by: string
  started_at: string | null
  completed_at: string | null
  error_message: string | null
  row_count: number | null
  run_metadata: Record<string, unknown>
  created_at: string
}

export interface ReportResultResponse {
  id: string
  run_id: string
  result_data: ReportResultRow[] | Record<string, unknown>
  result_hash: string
  export_path_csv: string | null
  export_path_excel: string | null
  export_path_pdf: string | null
  created_at: string
}

export type ReportResultRow = Record<string, unknown>
