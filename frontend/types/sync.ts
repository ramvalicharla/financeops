export type ConnectorType =
  | "ZOHO"
  | "TALLY"
  | "BUSY"
  | "MARG"
  | "MUNIM"
  | "QUICKBOOKS"
  | "XERO"
  | "GENERIC_FILE"

export type SyncRunStatus =
  | "PENDING"
  | "RUNNING"
  | "COMPLETED"
  | "HALTED"
  | "PAUSED"
  | "DUPLICATE_SYNC"
  | "CANCELLED"

export type DatasetType =
  | "TRIAL_BALANCE"
  | "GENERAL_LEDGER"
  | "BANK_STATEMENT"
  | "ACCOUNTS_RECEIVABLE"
  | "ACCOUNTS_PAYABLE"
  | "INVOICE_REGISTER"
  | "PURCHASE_REGISTER"
  | "PAYROLL_SUMMARY"
  | "CHART_OF_ACCOUNTS"
  | "VENDOR_MASTER"
  | "CUSTOMER_MASTER"
  | "GST_RETURN_GSTR1"
  | "FIXED_ASSET_REGISTER"

export interface ExternalConnection {
  id: string
  tenant_id: string
  connector_type: ConnectorType
  display_name: string
  last_sync_at: string | null
  last_sync_status: SyncRunStatus | null
  is_active: boolean
  created_at: string
}

export interface ValidationResult {
  category: string
  passed: boolean
  message: string | null
}

export interface SyncRun {
  id: string
  connection_id: string
  dataset_type: DatasetType
  status: SyncRunStatus
  started_at: string
  completed_at: string | null
  duration_seconds: number | null
  records_extracted: number | null
  drift_severity: "NONE" | "MINOR" | "SIGNIFICANT" | "CRITICAL" | null
  publish_event_id: string | null
  validation_results: ValidationResult[]
  error_message: string | null
}

export interface DriftChange {
  field: string
  previous_value: string
  current_value: string
  change_pct: number
}

export interface DriftReport {
  sync_run_id: string
  severity: "NONE" | "MINOR" | "SIGNIFICANT" | "CRITICAL"
  changes: DriftChange[]
  checked_at: string
}

export interface CreateConnectionInput {
  connector_type: ConnectorType
  display_name: string
  datasets: DatasetType[]
  schedule_mode: "manual" | "daily" | "weekly"
  schedule_time?: string
  schedule_day_of_week?: string
  oauth_connected?: boolean
  mapping?: Array<{
    source_column: string
    canonical_field: string
  }>
}

export interface TestConnectionInput {
  connector_type: ConnectorType
  display_name: string
  credentials?: Record<string, string>
  file_name?: string
}
