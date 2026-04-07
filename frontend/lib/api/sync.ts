import apiClient from "@/lib/api/client"
import type {
  CreateConnectionInput,
  DriftReport,
  ExternalConnection,
  OAuthCallbackResult,
  OAuthStartResult,
  SyncBootstrapResult,
  SyncRun,
  TestConnectionResult,
} from "@/types/sync"

type ConnectionListEnvelope = {
  items?: unknown[]
  data?: unknown[]
}

type SyncRunListEnvelope = {
  items?: unknown[]
  data?: unknown[]
}

const toConnectionStatus = (value: unknown): ExternalConnection["connection_status"] => {
  const normalized = String(value ?? "draft").trim().toLowerCase()
  if (normalized === "active") return "active"
  if (normalized === "suspended") return "suspended"
  if (normalized === "revoked") return "revoked"
  return "draft"
}

const toRunStatus = (value: unknown): SyncRun["status"] => {
  const normalized = String(value ?? "").trim().toLowerCase()
  if (normalized === "running") return "RUNNING"
  if (normalized === "completed" || normalized === "published") return "COMPLETED"
  if (normalized === "halted" || normalized === "failed" || normalized === "drift_alert") return "HALTED"
  if (normalized === "paused") return "PAUSED"
  return "PENDING"
}

const normalizeValidationResults = (value: unknown): SyncRun["validation_results"] => {
  const summary = value && typeof value === "object" ? (value as Record<string, unknown>) : {}
  const checks = Array.isArray(summary.checks) ? summary.checks : []
  return checks
    .map((item) => {
      if (!item || typeof item !== "object") {
        return null
      }
      const row = item as Record<string, unknown>
      return {
        category: String(row.category ?? "UNKNOWN"),
        passed: Boolean(row.passed),
        message: row.message == null ? null : String(row.message),
      }
    })
    .filter((item): item is NonNullable<typeof item> => item !== null)
}

const normalizeConnection = (value: unknown): ExternalConnection => {
  const row = value as Record<string, unknown>
  return {
    id: String(row.id ?? ""),
    connection_code: String(row.connection_code ?? ""),
    connection_name: String(row.connection_name ?? row.display_name ?? row.connection_code ?? "Connection"),
    connector_type: String(row.connector_type ?? ""),
    connection_status: toConnectionStatus(row.connection_status),
    source_system_instance_id:
      row.source_system_instance_id == null ? undefined : String(row.source_system_instance_id),
    created_at: row.created_at == null ? null : String(row.created_at),
  }
}

const normalizeSyncRun = (value: unknown): SyncRun => {
  const row = value as Record<string, unknown>
  return {
    id: String(row.id ?? ""),
    connection_id: String(row.connection_id ?? ""),
    dataset_type: String(row.dataset_type ?? "TRIAL_BALANCE").trim().toUpperCase() as SyncRun["dataset_type"],
    status: toRunStatus(row.run_status ?? row.status),
    started_at: String(row.created_at ?? new Date().toISOString()),
    completed_at: row.published_at == null ? null : String(row.published_at),
    duration_seconds: null,
    records_extracted:
      typeof row.extraction_fetched_records === "number"
        ? row.extraction_fetched_records
        : null,
    drift_severity: null,
    publish_event_id: null,
    validation_results: normalizeValidationResults(row.validation_summary_json),
    error_message: null,
  }
}

export const getConnections = async (): Promise<ExternalConnection[]> => {
  const response = await apiClient.get<ConnectionListEnvelope>("/api/v1/erp-sync/connections")
  const items = Array.isArray(response.data)
    ? response.data
    : response.data?.items ?? response.data?.data ?? []
  return items.map(normalizeConnection)
}

export const getConnection = async (id: string): Promise<ExternalConnection> => {
  const response = await apiClient.get<unknown>(`/api/v1/erp-sync/connections/${id}`)
  return normalizeConnection(response.data)
}

export const createConnection = async (
  payload: CreateConnectionInput,
): Promise<ExternalConnection> => {
  const response = await apiClient.post<unknown>("/api/v1/erp-sync/connections", payload)
  const connectionId =
    response.data && typeof response.data === "object"
      ? String((response.data as Record<string, unknown>).connection_id ?? "")
      : ""
  if (!connectionId) {
    throw new Error("Connection was created but no connection id was returned.")
  }
  return getConnection(connectionId)
}

export const startOAuth = async (
  connectionId: string,
  redirectUri: string,
): Promise<OAuthStartResult> => {
  const response = await apiClient.post<OAuthStartResult>(
    `/api/v1/erp-sync/connections/${connectionId}/oauth/start`,
    { redirect_uri: redirectUri },
  )
  return response.data
}

export const completeOAuth = async (
  connectionId: string,
  params: Record<string, string>,
): Promise<OAuthCallbackResult> => {
  const query = new URLSearchParams(params)
  const response = await apiClient.get<OAuthCallbackResult>(
    `/api/v1/erp-sync/connections/${connectionId}/oauth/callback?${query.toString()}`,
  )
  return response.data
}

export const testConnection = async (
  connectionId: string,
): Promise<TestConnectionResult> => {
  const response = await apiClient.post<TestConnectionResult>(
    `/api/v1/erp-sync/connections/${connectionId}/test`,
    {},
  )
  return response.data
}

export const activateConnection = async (
  connectionId: string,
): Promise<ExternalConnection> => {
  await apiClient.post(`/api/v1/erp-sync/connections/${connectionId}/activate`, {})
  return getConnection(connectionId)
}

export const getSyncRuns = async (connectionId: string): Promise<SyncRun[]> => {
  const response = await apiClient.get<SyncRunListEnvelope>(
    `/api/v1/erp-sync/sync-runs?connection_id=${encodeURIComponent(connectionId)}`,
  )
  const items = Array.isArray(response.data)
    ? response.data
    : response.data?.items ?? response.data?.data ?? []
  return items.map(normalizeSyncRun)
}

export const ensureTestReadySyncPath = async (
  connectionId: string,
): Promise<SyncBootstrapResult> => {
  const response = await apiClient.post<SyncBootstrapResult>(
    "/api/v1/erp-sync/bootstrap/test-ready",
    {
      connection_id: connectionId,
      dataset_type: "trial_balance",
    },
  )
  return response.data
}

export const triggerSync = async (
  connectionId: string,
): Promise<SyncRun> => {
  const bootstrap = await ensureTestReadySyncPath(connectionId)
  const response = await apiClient.post<unknown>("/api/v1/erp-sync/sync-runs", {
    connection_id: connectionId,
    sync_definition_id: bootstrap.sync_definition_id,
    sync_definition_version_id: bootstrap.sync_definition_version_id,
    dataset_type: "trial_balance",
  })
  return normalizeSyncRun(response.data)
}

export const getSyncRun = async (id: string): Promise<SyncRun> => {
  const response = await apiClient.get<unknown>(`/api/v1/erp-sync/sync-runs/${id}`)
  return normalizeSyncRun(response.data)
}

export const approvPublish = async (publishEventId: string): Promise<{ approved: boolean }> => {
  const response = await apiClient.post<{ approved: boolean }>(
    `/api/v1/erp-sync/publish-events/${publishEventId}/approve`,
    {},
  )
  return response.data
}

export const getDriftReport = async (syncRunId: string): Promise<DriftReport> => {
  const response = await apiClient.get<DriftReport>(
    `/api/v1/erp-sync/sync-runs/${syncRunId}/drift-report`,
  )
  return response.data
}
