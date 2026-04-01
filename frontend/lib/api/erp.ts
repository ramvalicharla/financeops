import apiClient from "@/lib/api/client"

export type ErpSyncType = "IMPORT" | "EXPORT"
export type ErpSyncModule = "COA" | "JOURNALS" | "VENDORS" | "CUSTOMERS"
export type ErpConnectorStatus = "ACTIVE" | "INACTIVE" | "ERROR"
export type ErpAuthType = "API_KEY" | "OAUTH" | "BASIC"

export interface ErpConnector {
  id: string
  tenant_id: string
  org_entity_id: string
  erp_type: string
  auth_type: ErpAuthType
  status: ErpConnectorStatus
  last_sync_at: string | null
  created_at: string
}

export interface ErpSyncJob {
  id: string
  tenant_id: string
  org_entity_id: string
  erp_connector_id: string
  sync_type: ErpSyncType
  module: ErpSyncModule
  status: "PENDING" | "RUNNING" | "SUCCESS" | "FAILED"
  started_at: string | null
  completed_at: string | null
  error_message: string | null
  retry_count: number
  result_summary: Record<string, unknown> | null
  created_at: string
}

export const listErpConnectors = async (): Promise<ErpConnector[]> => {
  const response = await apiClient.get<ErpConnector[]>("/api/v1/erp/connectors")
  return response.data
}

export const createErpConnector = async (payload: {
  org_entity_id: string
  erp_type: string
  auth_type: ErpAuthType
  connection_config: Record<string, unknown>
}): Promise<ErpConnector> => {
  const response = await apiClient.post<ErpConnector>("/api/v1/erp/connectors", payload)
  return response.data
}

export const testErpConnector = async (
  connectorId: string,
): Promise<{ connector_id: string; ok: boolean; result: Record<string, unknown> }> => {
  const response = await apiClient.post<{ connector_id: string; ok: boolean; result: Record<string, unknown> }>(
    `/api/v1/erp/connectors/${connectorId}/test`,
    {},
  )
  return response.data
}

export const updateErpConnectorStatus = async (
  connectorId: string,
  status: ErpConnectorStatus,
): Promise<ErpConnector> => {
  const response = await apiClient.patch<ErpConnector>(
    `/api/v1/erp/connectors/${connectorId}/status`,
    { status },
  )
  return response.data
}

export const listErpSyncJobs = async (params: {
  erp_connector_id?: string
} = {}): Promise<ErpSyncJob[]> => {
  const query = new URLSearchParams()
  if (params.erp_connector_id) {
    query.set("erp_connector_id", params.erp_connector_id)
  }
  const suffix = query.toString() ? `?${query.toString()}` : ""
  const response = await apiClient.get<ErpSyncJob[]>(`/api/v1/erp/sync/jobs${suffix}`)
  return response.data
}

export const runErpSync = async (payload: {
  erp_connector_id: string
  sync_type: ErpSyncType
  module: ErpSyncModule
  payload?: Record<string, unknown>
  retry_of_job_id?: string
}): Promise<ErpSyncJob> => {
  const response = await apiClient.post<ErpSyncJob>("/api/v1/erp/sync/run", payload)
  return response.data
}

export const importErpCoa = async (
  erpConnectorId: string,
): Promise<Record<string, unknown>> => {
  const response = await apiClient.post<Record<string, unknown>>(
    "/api/v1/erp/sync/coa/import",
    { erp_connector_id: erpConnectorId },
  )
  return response.data
}

export const mapErpCoa = async (payload: {
  erp_connector_id: string
  mappings: Array<{ erp_account_id: string; internal_account_id: string }>
}): Promise<{ upserted: number }> => {
  const response = await apiClient.post<{ upserted: number }>("/api/v1/erp/sync/coa/map", payload)
  return response.data
}

export const importErpJournals = async (payload: {
  erp_connector_id: string
  transactions?: Array<Record<string, unknown>>
}): Promise<Record<string, unknown>> => {
  const response = await apiClient.post<Record<string, unknown>>(
    "/api/v1/erp/sync/journals/import",
    payload,
  )
  return response.data
}

export const exportErpJournals = async (payload: {
  erp_connector_id: string
  journal_ids?: string[]
}): Promise<Record<string, unknown>> => {
  const response = await apiClient.post<Record<string, unknown>>(
    "/api/v1/erp/sync/journals/export",
    payload,
  )
  return response.data
}

export const syncErpVendors = async (payload: {
  erp_connector_id: string
  rows?: Array<Record<string, unknown>>
}): Promise<Record<string, unknown>> => {
  const response = await apiClient.post<Record<string, unknown>>("/api/v1/erp/sync/vendors", payload)
  return response.data
}

export const syncErpCustomers = async (payload: {
  erp_connector_id: string
  rows?: Array<Record<string, unknown>>
}): Promise<Record<string, unknown>> => {
  const response = await apiClient.post<Record<string, unknown>>("/api/v1/erp/sync/customers", payload)
  return response.data
}
