import apiClient from "@/lib/api/client"
import type {
  CreateConnectionInput,
  DatasetType,
  DriftReport,
  ExternalConnection,
  SyncRun,
  TestConnectionInput,
} from "@/types/sync"

export const getConnections = async (): Promise<ExternalConnection[]> => {
  const response = await apiClient.get<ExternalConnection[]>("/api/v1/erp-sync/connections")
  return response.data
}

export const getSyncRuns = async (connectionId: string): Promise<SyncRun[]> => {
  const response = await apiClient.get<SyncRun[]>(
    `/api/v1/erp-sync/sync-runs?connection_id=${encodeURIComponent(connectionId)}`,
  )
  return response.data
}

export const triggerSync = async (
  connectionId: string,
  datasetTypes: DatasetType[],
): Promise<SyncRun[]> => {
  const response = await apiClient.post<SyncRun[]>("/api/v1/erp-sync/sync-runs", {
    connection_id: connectionId,
    dataset_types: datasetTypes,
  })
  return response.data
}

export const getSyncRun = async (id: string): Promise<SyncRun> => {
  const response = await apiClient.get<SyncRun>(`/api/v1/erp-sync/sync-runs/${id}`)
  return response.data
}

export const approvPublish = async (publishEventId: string): Promise<{ approved: boolean }> => {
  const response = await apiClient.post<{ approved: boolean }>(
    `/api/v1/erp-sync/publish-events/${publishEventId}/approve`,
    {},
  )
  return response.data
}

export const getDriftReport = async (syncRunId: string): Promise<DriftReport> => {
  const response = await apiClient.get<DriftReport>(`/api/v1/erp-sync/drift/${syncRunId}`)
  return response.data
}

export const createConnection = async (
  payload: CreateConnectionInput,
): Promise<ExternalConnection> => {
  const response = await apiClient.post<ExternalConnection>(
    "/api/v1/erp-sync/connections",
    payload,
  )
  return response.data
}

export const testConnection = async (
  payload: TestConnectionInput,
): Promise<{ success: boolean; message?: string }> => {
  const response = await apiClient.post<{ success: boolean; message?: string }>(
    "/api/v1/erp-sync/connections/test",
    payload,
  )
  return response.data
}
