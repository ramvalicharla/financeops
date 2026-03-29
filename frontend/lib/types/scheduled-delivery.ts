export enum ScheduleType {
  BOARD_PACK = "BOARD_PACK",
  REPORT = "REPORT",
}

export enum RecipientType {
  EMAIL = "EMAIL",
  WEBHOOK = "WEBHOOK",
}

export enum DeliveryExportFormat {
  PDF = "PDF",
  EXCEL = "EXCEL",
  CSV = "CSV",
}

export enum DeliveryStatus {
  PENDING = "PENDING",
  RUNNING = "RUNNING",
  DELIVERED = "DELIVERED",
  FAILED = "FAILED",
}

export interface DeliveryRecipient {
  type: RecipientType
  address: string
}

export interface DeliveryScheduleResponse {
  id: string
  tenant_id: string
  name: string
  description: string | null
  schedule_type: ScheduleType
  source_definition_id: string
  cron_expression: string
  timezone: string
  recipients: DeliveryRecipient[]
  export_format: DeliveryExportFormat
  is_active: boolean
  last_triggered_at: string | null
  next_run_at: string | null
  config: Record<string, unknown>
  created_by: string
  created_at: string
  updated_at: string
}

export interface CreateDeliveryScheduleRequest {
  name: string
  description?: string | null
  schedule_type: ScheduleType
  source_definition_id: string
  cron_expression: string
  timezone?: string
  recipients: DeliveryRecipient[]
  export_format?: DeliveryExportFormat
  config?: Record<string, unknown>
}

export interface UpdateDeliveryScheduleRequest {
  name?: string
  description?: string | null
  schedule_type?: ScheduleType
  source_definition_id?: string
  cron_expression?: string
  timezone?: string
  recipients?: DeliveryRecipient[]
  export_format?: DeliveryExportFormat
  is_active?: boolean
  config?: Record<string, unknown>
}

export interface TriggerDeliveryResponse {
  schedule_id: string
  status: "triggered"
}

export interface DeliveryLogResponse {
  id: string
  tenant_id: string
  schedule_id: string
  triggered_at: string
  completed_at: string | null
  status: DeliveryStatus
  channel_type: "EMAIL" | "WEBHOOK"
  recipient_address: string
  source_run_id: string | null
  error_message: string | null
  retry_count: number
  response_metadata: Record<string, unknown>
  created_at: string
}
