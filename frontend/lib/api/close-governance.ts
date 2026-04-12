import apiClient from "@/lib/api/client"

export type LockType = "SOFT_CLOSED" | "HARD_CLOSED"

export interface PeriodLockRequest {
  org_entity_id?: string
  fiscal_year: number
  period_number: number
  lock_type: LockType
  reason?: string
}

export interface UnlockPeriodRequest {
  org_entity_id?: string
  fiscal_year: number
  period_number: number
  reason: string
}

export interface ChecklistReadiness {
  pass: boolean
  blockers: string[]
  warnings: string[]
  metrics: {
    pending_journals: number
    trial_balance_total_debit: string
    trial_balance_total_credit: string
    fx_entities_exist: boolean
    revaluation_done: boolean
    translation_done: boolean
    group_exists: boolean
    consolidation_done: boolean
    coa_present: boolean
  }
}

export interface CloseChecklistItem {
  checklist_type: string
  checklist_status: "PENDING" | "COMPLETED" | "FAILED"
  completed_by: string | null
  completed_at: string | null
  evidence_json: Record<string, unknown> | null
}

export interface PeriodStatusResponse {
  period_id: string | null
  org_entity_id: string | null
  fiscal_year: number
  period_number: number
  period_start: string
  period_end: string
  status: string
  reason: string | null
  locked_at: string | null
  locked_by: string | null
}

export interface CloseChecklistResponse {
  period_id: string
  fiscal_year: number
  period_number: number
  org_entity_id: string
  items: CloseChecklistItem[]
  readiness: ChecklistReadiness
}

export interface MonthendChecklistSummary {
  checklist_id: string
  period_year: number
  period_month: number
  entity_name: string
  status: string
  created_at: string
}

export interface MonthendChecklistTask {
  task_id: string
  task_name: string
  task_category: string
  priority: string
  status: string
  assigned_to: string | null
  sort_order: number
  is_required: boolean
  completed_at: string | null
}

export interface MonthendChecklistDetail extends MonthendChecklistSummary {
  closed_at: string | null
  tasks: MonthendChecklistTask[]
}

export interface MonthendChecklistListResponse {
  checklists: MonthendChecklistSummary[]
  count: number
}

export const getPeriodStatus = async (params: {
  fiscal_year: number
  period_number: number
  org_entity_id?: string
}): Promise<PeriodStatusResponse> => {
  const search = new URLSearchParams({
    fiscal_year: String(params.fiscal_year),
    period_number: String(params.period_number),
  })
  if (params.org_entity_id) search.set("org_entity_id", params.org_entity_id)
  const response = await apiClient.get<PeriodStatusResponse>(
    `/api/v1/close/period-status?${search.toString()}`,
  )
  return response.data
}

export const lockPeriod = async (
  body: PeriodLockRequest,
): Promise<Record<string, unknown>> => {
  const response = await apiClient.post<Record<string, unknown>>(
    "/api/v1/close/lock-period",
    body,
  )
  return response.data
}

export const unlockPeriod = async (
  body: UnlockPeriodRequest,
): Promise<Record<string, unknown>> => {
  const response = await apiClient.post<Record<string, unknown>>(
    "/api/v1/close/unlock-period",
    body,
  )
  return response.data
}

export const runReadiness = async (body: {
  org_entity_id: string
  fiscal_year: number
  period_number: number
}): Promise<ChecklistReadiness> => {
  const response = await apiClient.post<ChecklistReadiness>(
    "/api/v1/close/run-readiness",
    body,
  )
  return response.data
}

export const getCloseChecklist = async (params: {
  org_entity_id: string
  fiscal_year: number
  period_number: number
}): Promise<CloseChecklistResponse> => {
  const search = new URLSearchParams({
    org_entity_id: params.org_entity_id,
    fiscal_year: String(params.fiscal_year),
    period_number: String(params.period_number),
  })
  const response = await apiClient.get<CloseChecklistResponse>(
    `/api/v1/close/checklist?${search.toString()}`,
  )
  return response.data
}

export const completeChecklistItem = async (body: {
  org_entity_id: string
  fiscal_year: number
  period_number: number
  checklist_type: string
  evidence_json?: Record<string, unknown>
}): Promise<Record<string, unknown>> => {
  const response = await apiClient.post<Record<string, unknown>>(
    "/api/v1/close/checklist/complete",
    body,
  )
  return response.data
}

export const getMonthendChecklists = async (params: {
  entity_name?: string
  checklist_status?: string
  limit?: number
  offset?: number
}): Promise<MonthendChecklistListResponse> => {
  const search = new URLSearchParams()
  if (params.entity_name) search.set("entity_name", params.entity_name)
  if (params.checklist_status) search.set("checklist_status", params.checklist_status)
  if (typeof params.limit === "number") search.set("limit", String(params.limit))
  if (typeof params.offset === "number") search.set("offset", String(params.offset))
  const response = await apiClient.get<MonthendChecklistListResponse>(
    `/api/v1/monthend/?${search.toString()}`,
  )
  return response.data
}

export const getMonthendChecklist = async (checklistId: string): Promise<MonthendChecklistDetail> => {
  const response = await apiClient.get<MonthendChecklistDetail>(`/api/v1/monthend/${checklistId}`)
  return response.data
}

export const updateMonthendChecklistTaskStatus = async (params: {
  checklistId: string
  taskId: string
  status: string
  notes?: string | null
}): Promise<Record<string, unknown>> => {
  const response = await apiClient.patch<Record<string, unknown>>(
    `/api/v1/monthend/${params.checklistId}/tasks/${params.taskId}`,
    {
      status: params.status,
      notes: params.notes ?? null,
    },
  )
  return response.data
}

export const closeMonthendChecklist = async (params: {
  checklistId: string
  notes?: string | null
}): Promise<Record<string, unknown>> => {
  const response = await apiClient.post<Record<string, unknown>>(
    `/api/v1/monthend/${params.checklistId}/close`,
    {
      notes: params.notes ?? null,
    },
  )
  return response.data
}
