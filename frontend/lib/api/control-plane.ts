import apiClient from "@/lib/api/client"

export interface ControlPlaneEntity {
  id: string
  entity_code: string
  entity_name: string
  organisation_id: string
}

export interface ControlPlaneIntent {
  intent_id: string
  intent_type: string
  status: string
  module_key: string
  target_type: string
  target_id: string | null
  org_id: string
  entity_id: string
  requested_by_user_id: string
  requested_by_role: string
  requested_at: string | null
  submitted_at: string | null
  validated_at: string | null
  approved_at: string | null
  executed_at: string | null
  recorded_at: string | null
  rejected_at: string | null
  rejection_reason: string | null
  source_channel: string
  job_id: string | null
  record_refs: Record<string, unknown> | null
  guard_results: Record<string, unknown> | null
  payload: Record<string, unknown> | null
  next_action: string | null
  events?: Array<{
    event_id: string
    event_type: string
    from_status: string | null
    to_status: string | null
    actor_user_id: string | null
    actor_role: string | null
    event_at: string | null
    payload: Record<string, unknown> | null
  }>
}

export interface ControlPlaneJob {
  job_id: string
  intent_id: string
  entity_id: string | null
  job_type: string
  status: string
  runner_type: string
  queue_name: string
  requested_at: string | null
  started_at: string | null
  finished_at: string | null
  failed_at: string | null
  retry_count: number
  max_retries: number
  error_code: string | null
  error_message: string | null
  error_details: Record<string, unknown> | null
}

export interface AirlockItem {
  airlock_item_id: string
  entity_id: string | null
  source_type: string
  source_reference: string | null
  file_name: string | null
  mime_type: string | null
  size_bytes: number | null
  checksum_sha256: string | null
  status: string
  submitted_by_user_id: string
  reviewed_by_user_id: string | null
  admitted_by_user_id: string | null
  submitted_at: string | null
  reviewed_at: string | null
  admitted_at: string | null
  rejected_at: string | null
  rejection_reason: string | null
  metadata: Record<string, unknown> | null
  findings: Array<Record<string, unknown>>
}

export interface AirlockMutationResult {
  airlock_item_id: string
  status: string
  admitted: boolean
  checksum_sha256: string | null
}

export const listControlPlaneEntities = async (): Promise<ControlPlaneEntity[]> => {
  const response = await apiClient.get<ControlPlaneEntity[]>("/api/v1/platform/entities")
  return response.data
}

export const listIntents = async (params?: {
  entity_id?: string
  status?: string
  limit?: number
}): Promise<ControlPlaneIntent[]> => {
  const search = new URLSearchParams()
  if (params?.entity_id) search.set("entity_id", params.entity_id)
  if (params?.status) search.set("status", params.status)
  if (params?.limit !== undefined) search.set("limit", String(params.limit))
  const suffix = search.toString()
  const response = await apiClient.get<ControlPlaneIntent[]>(
    `/api/v1/platform/control-plane/intents${suffix ? `?${suffix}` : ""}`,
  )
  return response.data
}

export const getIntent = async (intentId: string): Promise<ControlPlaneIntent> => {
  const response = await apiClient.get<ControlPlaneIntent>(
    `/api/v1/platform/control-plane/intents/${intentId}`,
  )
  return response.data
}

export const listJobs = async (params?: {
  entity_id?: string
  status?: string
  limit?: number
}): Promise<ControlPlaneJob[]> => {
  const search = new URLSearchParams()
  if (params?.entity_id) search.set("entity_id", params.entity_id)
  if (params?.status) search.set("status", params.status)
  if (params?.limit !== undefined) search.set("limit", String(params.limit))
  const suffix = search.toString()
  const response = await apiClient.get<ControlPlaneJob[]>(
    `/api/v1/platform/control-plane/jobs${suffix ? `?${suffix}` : ""}`,
  )
  return response.data
}

export const listAirlockItems = async (params?: {
  entity_id?: string
  status?: string
  limit?: number
}): Promise<AirlockItem[]> => {
  const search = new URLSearchParams()
  if (params?.entity_id) search.set("entity_id", params.entity_id)
  if (params?.status) search.set("status", params.status)
  if (params?.limit !== undefined) search.set("limit", String(params.limit))
  const suffix = search.toString()
  const response = await apiClient.get<AirlockItem[]>(
    `/api/v1/platform/control-plane/airlock${suffix ? `?${suffix}` : ""}`,
  )
  return response.data
}

export const getAirlockItem = async (itemId: string): Promise<AirlockItem> => {
  const response = await apiClient.get<AirlockItem>(
    `/api/v1/platform/control-plane/airlock/${itemId}`,
  )
  return response.data
}

export const admitAirlockItem = async (itemId: string): Promise<AirlockMutationResult> => {
  const response = await apiClient.post<AirlockMutationResult>(
    `/api/v1/platform/control-plane/airlock/${itemId}/admit`,
    {},
  )
  return response.data
}

export const rejectAirlockItem = async (
  itemId: string,
  reason: string,
): Promise<AirlockMutationResult> => {
  const response = await apiClient.post<AirlockMutationResult>(
    `/api/v1/platform/control-plane/airlock/${itemId}/reject`,
    { reason },
  )
  return response.data
}
