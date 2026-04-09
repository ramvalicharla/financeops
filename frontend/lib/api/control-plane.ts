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

export interface TimelineEvent {
  timeline_type: string
  occurred_at: string
  subject_type: string | null
  subject_id: string | null
  module_key: string | null
  entity_id?: string | null
  actor_user_id?: string | null
  payload: Record<string, unknown> | null
}

export interface GovernanceSnapshotInput {
  snapshot_input_id: string
  input_type: string
  input_ref: string
  input_hash: string | null
  input_payload: Record<string, unknown> | null
}

export interface GovernanceSnapshot {
  snapshot_id: string
  module_key: string
  snapshot_kind: string
  subject_type: string
  subject_id: string
  entity_id: string | null
  version_no: number
  determinism_hash: string
  replay_supported: boolean
  trigger_event: string | null
  snapshot_at: string | null
  payload: Record<string, unknown> | null
  comparison_payload: Record<string, unknown> | null
  inputs?: GovernanceSnapshotInput[]
  metadata?: Record<string, unknown>
  replay?: Record<string, unknown>
}

export interface SnapshotComparison {
  left_snapshot_id: string
  right_snapshot_id: string
  same_subject: boolean
  same_hash: boolean
  left_hash: string
  right_hash: string
  left_version: number
  right_version: number
  comparison: {
    left: Record<string, unknown> | null
    right: Record<string, unknown> | null
  }
}

export interface LineageGraph {
  subject_type: string
  subject_id: string
  forward: {
    root_run_id?: string
    nodes: Array<Record<string, unknown>>
    edges: Array<Record<string, unknown>>
  }
  reverse: {
    root_run_id?: string
    nodes: Array<Record<string, unknown>>
    edges: Array<Record<string, unknown>>
  }
}

export interface ImpactSummary {
  subject_type: string
  subject_id: string
  impacted_count: number
  impacted_reports_count: number
  warning: string
  impacted_nodes: Array<Record<string, unknown>>
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

export const listTimeline = async (params?: {
  entity_id?: string
  subject_type?: string
  subject_id?: string
  limit?: number
}): Promise<TimelineEvent[]> => {
  const search = new URLSearchParams()
  if (params?.entity_id) search.set("entity_id", params.entity_id)
  if (params?.subject_type) search.set("subject_type", params.subject_type)
  if (params?.subject_id) search.set("subject_id", params.subject_id)
  if (params?.limit !== undefined) search.set("limit", String(params.limit))
  const suffix = search.toString()
  const response = await apiClient.get<TimelineEvent[]>(
    `/api/v1/platform/control-plane/timeline${suffix ? `?${suffix}` : ""}`,
  )
  return response.data
}

export const exportTimeline = async (params?: {
  entity_id?: string
  subject_type?: string
  subject_id?: string
  limit?: number
}): Promise<Blob> => {
  const search = new URLSearchParams()
  if (params?.entity_id) search.set("entity_id", params.entity_id)
  if (params?.subject_type) search.set("subject_type", params.subject_type)
  if (params?.subject_id) search.set("subject_id", params.subject_id)
  if (params?.limit !== undefined) search.set("limit", String(params.limit))
  const suffix = search.toString()
  const response = await apiClient.get(
    `/api/v1/platform/control-plane/timeline/export${suffix ? `?${suffix}` : ""}`,
    { responseType: "blob" },
  )
  return response.data as Blob
}

export const getDeterminism = async (subjectType: string, subjectId: string): Promise<GovernanceSnapshot> => {
  const search = new URLSearchParams({ subject_type: subjectType, subject_id: subjectId })
  const response = await apiClient.get<GovernanceSnapshot>(
    `/api/v1/platform/control-plane/determinism?${search.toString()}`,
  )
  return response.data
}

export const getLineage = async (subjectType: string, subjectId: string): Promise<LineageGraph> => {
  const search = new URLSearchParams({ subject_type: subjectType, subject_id: subjectId })
  const response = await apiClient.get<LineageGraph>(
    `/api/v1/platform/control-plane/lineage?${search.toString()}`,
  )
  return response.data
}

export const getImpact = async (subjectType: string, subjectId: string): Promise<ImpactSummary> => {
  const search = new URLSearchParams({ subject_type: subjectType, subject_id: subjectId })
  const response = await apiClient.get<ImpactSummary>(
    `/api/v1/platform/control-plane/impact?${search.toString()}`,
  )
  return response.data
}

export const listSnapshots = async (params?: {
  entity_id?: string
  subject_type?: string
  limit?: number
}): Promise<GovernanceSnapshot[]> => {
  const search = new URLSearchParams()
  if (params?.entity_id) search.set("entity_id", params.entity_id)
  if (params?.subject_type) search.set("subject_type", params.subject_type)
  if (params?.limit !== undefined) search.set("limit", String(params.limit))
  const suffix = search.toString()
  const response = await apiClient.get<GovernanceSnapshot[]>(
    `/api/v1/platform/control-plane/snapshots${suffix ? `?${suffix}` : ""}`,
  )
  return response.data
}

export const createManualSnapshot = async (
  subjectType: string,
  subjectId: string,
): Promise<GovernanceSnapshot> => {
  const response = await apiClient.post<GovernanceSnapshot>(
    "/api/v1/platform/control-plane/snapshots/manual",
    { subject_type: subjectType, subject_id: subjectId },
  )
  return response.data
}

export const getSnapshot = async (snapshotId: string): Promise<GovernanceSnapshot> => {
  const response = await apiClient.get<GovernanceSnapshot>(
    `/api/v1/platform/control-plane/snapshots/${snapshotId}`,
  )
  return response.data
}

export const compareSnapshots = async (
  snapshotId: string,
  otherSnapshotId: string,
): Promise<SnapshotComparison> => {
  const response = await apiClient.get<SnapshotComparison>(
    `/api/v1/platform/control-plane/snapshots/${snapshotId}/compare/${otherSnapshotId}`,
  )
  return response.data
}

export const getAuditPack = async (subjectType: string, subjectId: string): Promise<Blob> => {
  const search = new URLSearchParams({ subject_type: subjectType, subject_id: subjectId })
  const response = await apiClient.get(
    `/api/v1/platform/control-plane/audit-pack?${search.toString()}`,
    { responseType: "blob" },
  )
  return response.data as Blob
}
