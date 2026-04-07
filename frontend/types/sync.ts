export type ConnectorType =
  | "ZOHO"
  | "TALLY"
  | "BUSY"
  | "MARG"
  | "MUNIM"
  | "QUICKBOOKS"
  | "XERO"
  | "GENERIC_FILE"

export type BackendConnectorType =
  | "zoho"
  | "tally"
  | "busy"
  | "marg"
  | "munim"
  | "quickbooks"
  | "xero"
  | "generic_file"

export type ConnectionStatus = "draft" | "active" | "suspended" | "revoked"

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
  connection_code: string
  connection_name: string
  connector_type: BackendConnectorType | string
  connection_status: ConnectionStatus
  source_system_instance_id?: string
  created_at?: string | null
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
  connector_type: "zoho" | "quickbooks"
  connection_code: string
  connection_name: string
  client_id: string
  client_secret: string
  organization_id?: string
  realm_id?: string
  use_sandbox?: boolean
  entity_id?: string
}

export interface OAuthStartResult {
  authorization_url: string
  state_token: string
  expires_at: string
}

export interface OAuthCallbackResult {
  connection_id: string
  provider: string
  token_expires_at: string
  scopes: string | null
  status: "connected"
}

export interface TestConnectionResult {
  ok: boolean
  connector_type: string
  realm_id?: string
  organization_id?: string
  company_info?: unknown
}

export interface SyncBootstrapResult {
  connection_id: string
  connection_status: string
  mapping_definition_id: string
  mapping_version_id: string
  sync_definition_id: string
  sync_definition_version_id: string
}
