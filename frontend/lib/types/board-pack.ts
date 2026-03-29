export enum SectionType {
  PROFIT_AND_LOSS = "PROFIT_AND_LOSS",
  BALANCE_SHEET = "BALANCE_SHEET",
  CASH_FLOW = "CASH_FLOW",
  KPI_SUMMARY = "KPI_SUMMARY",
  RATIO_ANALYSIS = "RATIO_ANALYSIS",
  NARRATIVE = "NARRATIVE",
  FX_SUMMARY = "FX_SUMMARY",
  ENTITY_CONSOLIDATION = "ENTITY_CONSOLIDATION",
}

export enum PeriodType {
  MONTHLY = "MONTHLY",
  QUARTERLY = "QUARTERLY",
  ANNUAL = "ANNUAL",
}

export enum PackRunStatus {
  PENDING = "PENDING",
  RUNNING = "RUNNING",
  COMPLETE = "COMPLETE",
  FAILED = "FAILED",
}

export interface DefinitionResponse {
  id: string
  tenant_id: string
  name: string
  description: string | null
  section_types: string[]
  entity_ids: string[]
  period_type: string
  config: Record<string, unknown>
  created_by: string
  created_at: string
  updated_at: string
  is_active: boolean
}

export interface CreateDefinitionRequest {
  name: string
  description?: string | null
  section_types: SectionType[]
  entity_ids: string[]
  period_type: PeriodType
  config?: Record<string, unknown>
}

export interface UpdateDefinitionRequest {
  name?: string
  description?: string | null
  section_types?: SectionType[]
  entity_ids?: string[]
  config?: Record<string, unknown>
}

export interface GenerateRequest {
  definition_id: string
  period_start: string
  period_end: string
}

export interface RunResponse {
  id: string
  tenant_id: string
  definition_id: string
  period_start: string
  period_end: string
  status: PackRunStatus
  triggered_by: string
  started_at: string | null
  completed_at: string | null
  error_message: string | null
  chain_hash: string | null
  run_metadata: Record<string, unknown>
  created_at: string
}

export interface SectionResponse {
  id: string
  run_id: string
  section_type: string
  section_order: number
  title: string
  section_hash: string
  rendered_at: string
  data_snapshot?: Record<string, unknown> | null
}

export interface ArtifactResponse {
  id: string
  run_id: string
  format: string
  storage_path: string
  file_size_bytes: number | null
  generated_at: string
  checksum: string | null
}
