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

type EnvelopeList = {
  items?: unknown[]
  data?: unknown[]
}

type BootstrapSyncPath = {
  sync_definition_id?: unknown
  sync_definition_version_id?: unknown
}

const ERP_FEATURE_NOT_IMPLEMENTED_MESSAGE = "ERP feature not yet supported"
const ERP_RESPONSE_SHAPE_ERROR = "Unexpected ERP API response shape"
const DEFAULT_AUTH_TYPE: ErpAuthType = "API_KEY"
const ERP_MISSING_ID_ERROR = "Missing ID in ERP API response"

const isRecord = (value: unknown): value is Record<string, unknown> =>
  value !== null && typeof value === "object"

const toRecord = (value: unknown): Record<string, unknown> => (isRecord(value) ? value : {})

const toStringValue = (value: unknown): string =>
  typeof value === "string" ? value : value == null ? "" : String(value)

const toNullableString = (value: unknown): string | null => {
  const text = toStringValue(value).trim()
  return text ? text : null
}

const debugErpApiCall = (method: string, path: string, payload?: unknown) => {
  console.debug("ERP API call", {
    method,
    path,
    payload,
  })
}

const debugErpApiResponse = (path: string, response: unknown) => {
  console.debug("ERP API response", {
    path,
    response,
  })
}

const throwUnexpectedShape = (): never => {
  throw new Error(ERP_RESPONSE_SHAPE_ERROR)
}

const extractList = (value: unknown): unknown[] => {
  if (Array.isArray(value)) {
    return value
  }

  const envelope = toRecord(value) as EnvelopeList
  if (Array.isArray(envelope.items)) {
    return envelope.items
  }
  if (Array.isArray(envelope.data)) {
    return envelope.data
  }

  return []
}

const requireId = (value: unknown): string => {
  const row = toRecord(value)
  const id = toStringValue(
    row.id ??
      row.connection_id ??
      row.job_id ??
      toRecord(row.record_refs).sync_run_id,
  )
  if (!id) {
    throw new Error(ERP_MISSING_ID_ERROR)
  }
  return id
}

const normalizeConnection = (value: unknown): {
  id: string
  name: string
  status: string
} => {
  const row = toRecord(value)
  return {
    id: toStringValue(row.id ?? row.connection_id),
    name: toStringValue(row.name ?? row.connection_name),
    status: toStringValue(row.status ?? row.connection_status),
  }
}

const normalizeSyncRun = (value: unknown): {
  id: string
  status: string
} => {
  const row = toRecord(value)
  return {
    id: toStringValue(
      row.id ??
        row.job_id ??
        toRecord(row.record_refs).sync_run_id,
    ),
    status: toStringValue(row.status ?? row.state ?? row.run_status),
  }
}

const normalizeConnectorStatus = (value: unknown): ErpConnectorStatus => {
  const normalized = toStringValue(value).trim().toLowerCase()
  if (normalized === "active") {
    return "ACTIVE"
  }
  if (normalized === "failed" || normalized === "error" || normalized === "drift_alert") {
    return "ERROR"
  }
  return "INACTIVE"
}

const normalizeRunStatus = (value: unknown): ErpSyncJob["status"] => {
  const normalized = toStringValue(value).trim().toLowerCase()
  if (normalized === "running") {
    return "RUNNING"
  }
  if (normalized === "completed" || normalized === "published" || normalized === "success") {
    return "SUCCESS"
  }
  if (normalized === "failed" || normalized === "halted" || normalized === "paused" || normalized === "drift_alert") {
    return "FAILED"
  }
  return "PENDING"
}

const normalizeDatasetType = (module: ErpSyncModule): string => {
  if (module === "COA") {
    return "chart_of_accounts"
  }
  if (module === "JOURNALS") {
    return "general_ledger"
  }
  if (module === "VENDORS") {
    return "vendor_master"
  }
  return "customer_master"
}

const normalizeSyncModule = (value: unknown): ErpSyncModule => {
  const normalized = toStringValue(value).trim().toLowerCase()
  if (normalized === "chart_of_accounts") {
    return "COA"
  }
  if (normalized === "vendor_master") {
    return "VENDORS"
  }
  if (normalized === "customer_master") {
    return "CUSTOMERS"
  }
  return "JOURNALS"
}

const generateConnectionCode = (erpType: string): string => {
  const connectorType = toStringValue(erpType).trim().toLowerCase() || "connector"
  const suffix =
    typeof globalThis.crypto?.randomUUID === "function"
      ? globalThis.crypto.randomUUID().slice(0, 8)
      : `${Date.now()}`
  return `${connectorType}-${suffix}`
}

const extractCredentials = (
  value: Record<string, unknown> | undefined,
): Record<string, unknown> => {
  const config = toRecord(value)
  const credentials = toRecord(config.credentials)
  return credentials
}

const validateNormalizedConnection = (value: {
  id: string
  name: string
  status: string
}) => {
  if (!value.id || !value.name || !value.status) {
    throw new Error("Invalid connection response shape")
  }
}

const validateNormalizedSyncRun = (value: {
  id: string
  status: string
}) => {
  if (!value.id || !value.status) {
    throw new Error("Invalid sync run response shape")
  }
}

const validateTestConnectorResponse = (value: { success?: boolean; status?: string }) => {
  if (typeof value.success === "boolean" || Boolean(value.status)) {
    return
  }
  throwUnexpectedShape()
}

const toErpConnector = (
  value: unknown,
  overrides: Partial<ErpConnector> = {},
): ErpConnector => {
  const row = toRecord(value)
  const normalized = normalizeConnection(row)
  validateNormalizedConnection(normalized)
  return {
    id: normalized.id,
    tenant_id: toStringValue(row.tenant_id ?? overrides.tenant_id ?? ""),
    org_entity_id: toStringValue(row.entity_id ?? row.org_entity_id ?? overrides.org_entity_id ?? ""),
    erp_type: toStringValue(row.connector_type ?? row.erp_type ?? overrides.erp_type ?? "").trim().toUpperCase(),
    auth_type: (toStringValue(row.auth_type ?? overrides.auth_type ?? DEFAULT_AUTH_TYPE).trim().toUpperCase() ||
      DEFAULT_AUTH_TYPE) as ErpAuthType,
    status: normalizeConnectorStatus(normalized.status ?? overrides.status),
    last_sync_at: toNullableString(row.last_sync_at ?? overrides.last_sync_at),
    created_at:
      toNullableString(row.created_at ?? overrides.created_at) ?? new Date().toISOString(),
  }
}

const getErpConnector = async (
  connectorId: string,
  overrides: Partial<ErpConnector> = {},
): Promise<ErpConnector> => {
  const path = `/api/v1/erp-sync/connections/${connectorId}`
  debugErpApiCall("GET", path)
  const response = await apiClient.get<unknown>(path)
  debugErpApiResponse(path, response.data)

  return toErpConnector(response.data, overrides)
}

const toErpSyncJob = (
  value: unknown,
  context: {
    erp_connector_id?: string
    sync_type?: ErpSyncType
    module?: ErpSyncModule
  } = {},
): ErpSyncJob => {
  const row = toRecord(value)
  const normalized = normalizeSyncRun(row)
  validateNormalizedSyncRun(normalized)
  const datasetType = row.dataset_type ?? row.module
  return {
    id: normalized.id,
    tenant_id: toStringValue(row.tenant_id ?? ""),
    org_entity_id: toStringValue(row.entity_id ?? row.org_entity_id ?? ""),
    erp_connector_id: toStringValue(row.connection_id ?? row.erp_connector_id ?? context.erp_connector_id ?? ""),
    sync_type: context.sync_type ?? "IMPORT",
    module: context.module ?? normalizeSyncModule(datasetType),
    status: normalizeRunStatus(normalized.status),
    started_at: toNullableString(row.started_at ?? row.created_at),
    completed_at: toNullableString(row.completed_at ?? row.published_at),
    error_message: toNullableString(row.error_message),
    retry_count: typeof row.retry_count === "number" ? row.retry_count : 0,
    result_summary: isRecord(row.validation_summary_json)
      ? row.validation_summary_json
      : isRecord(row.record_refs)
        ? row.record_refs
        : null,
    created_at: toNullableString(row.created_at) ?? new Date().toISOString(),
  }
}

const ensureBootstrapSyncPath = async (
  connectorId: string,
  datasetType: string,
  payload?: Record<string, unknown>,
): Promise<{ sync_definition_id: string; sync_definition_version_id: string }> => {
  const path = "/api/v1/erp-sync/bootstrap/test-ready"
  const requestPayload: Record<string, unknown> = {
    connection_id: connectorId,
    dataset_type: datasetType,
  }

  const entityId = payload?.entity_id ?? payload?.org_entity_id
  if (typeof entityId === "string" && entityId.trim()) {
    requestPayload.entity_id = entityId
  }

  debugErpApiCall("POST", path, requestPayload)
  const response = await apiClient.post<BootstrapSyncPath>(path, requestPayload)
  debugErpApiResponse(path, response.data)

  const bootstrap = toRecord(response.data)
  const syncDefinitionId = toStringValue(bootstrap.sync_definition_id)
  const syncDefinitionVersionId = toStringValue(bootstrap.sync_definition_version_id)
  if (!syncDefinitionId || !syncDefinitionVersionId) {
    throwUnexpectedShape()
  }

  return {
    sync_definition_id: syncDefinitionId,
    sync_definition_version_id: syncDefinitionVersionId,
  }
}

const warnUnsupportedErpFeature = (): never => {
  console.warn("ERP feature not implemented in backend")
  throw new Error(ERP_FEATURE_NOT_IMPLEMENTED_MESSAGE)
}

export const listErpConnectors = async (): Promise<ErpConnector[]> => {
  const path = "/api/v1/erp-sync/connections"
  debugErpApiCall("GET", path)
  const response = await apiClient.get<unknown>(path)
  debugErpApiResponse(path, response.data)

  const rows = extractList(response.data)
  return rows.map((value) => toErpConnector(value))
}

export const createErpConnector = async (payload: {
  org_entity_id: string
  erp_type: string
  auth_type: ErpAuthType
  connection_config: Record<string, unknown>
}): Promise<ErpConnector> => {
  const path = "/api/v1/erp-sync/connections"
  const credentials = extractCredentials(payload.connection_config)
  const requestPayload: Record<string, unknown> = {
    entity_id: payload.org_entity_id,
    connector_type: payload.erp_type.trim().toLowerCase(),
    connection_code: generateConnectionCode(payload.erp_type),
    connection_name: payload.erp_type,
    ...credentials,
  }

  debugErpApiCall("POST", path, requestPayload)
  const response = await apiClient.post<unknown>(path, requestPayload)
  debugErpApiResponse(path, response.data)

  const connectorId = requireId(response.data)

  return getErpConnector(connectorId, {
    auth_type: payload.auth_type,
    org_entity_id: payload.org_entity_id,
    erp_type: payload.erp_type,
  })
}

export const testErpConnector = async (
  connectorId: string,
): Promise<{ connector_id: string; ok: boolean; result: Record<string, unknown> }> => {
  const path = `/api/v1/erp-sync/connections/${connectorId}/test`
  debugErpApiCall("POST", path, {})
  const response = await apiClient.post<unknown>(path, {})
  debugErpApiResponse(path, response.data)

  const data = toRecord(response.data)
  const responseConnectorId = requireId(data)
  validateTestConnectorResponse({
    success:
      typeof data.success === "boolean"
        ? data.success
        : typeof data.ok === "boolean"
          ? data.ok
          : undefined,
    status: toNullableString(data.status) ?? undefined,
  })

  return {
    connector_id: responseConnectorId,
    ok: typeof data.ok === "boolean" ? data.ok : Boolean(data.success),
    result: toRecord(data.result),
  }
}

export const updateErpConnectorStatus = async (
  connectorId: string,
  status: ErpConnectorStatus,
): Promise<ErpConnector> => {
  const normalizedStatus = toStringValue(status).trim().toUpperCase()
  let path = ""

  if (normalizedStatus === "ACTIVE") {
    path = `/api/v1/erp-sync/connections/${connectorId}/activate`
  } else if (normalizedStatus === "INACTIVE") {
    path = `/api/v1/erp-sync/connections/${connectorId}/suspend`
  } else {
    throw new Error("Unsupported connector status transition")
  }

  debugErpApiCall("POST", path, {})
  const response = await apiClient.post<unknown>(path, {})
  debugErpApiResponse(path, response.data)
  requireId(response.data)

  return getErpConnector(connectorId)
}

export const listErpSyncJobs = async (params: {
  erp_connector_id?: string
} = {}): Promise<ErpSyncJob[]> => {
  const query = new URLSearchParams()
  if (params.erp_connector_id) {
    query.set("connection_id", params.erp_connector_id)
  }
  const suffix = query.toString() ? `?${query.toString()}` : ""
  const path = `/api/v1/erp-sync/sync-runs${suffix}`

  debugErpApiCall("GET", path)
  const response = await apiClient.get<unknown>(path)
  debugErpApiResponse(path, response.data)

  const rows = extractList(response.data)
  return rows.map((value) =>
    toErpSyncJob(value, { erp_connector_id: params.erp_connector_id }),
  )
}

export const runErpSync = async (payload: {
  erp_connector_id: string
  sync_type: ErpSyncType
  module: ErpSyncModule
  payload?: Record<string, unknown>
  retry_of_job_id?: string
}): Promise<ErpSyncJob> => {
  const datasetType = normalizeDatasetType(payload.module)
  const bootstrap = await ensureBootstrapSyncPath(
    payload.erp_connector_id,
    datasetType,
    payload.payload,
  )

  const path = "/api/v1/erp-sync/sync-runs"
  const requestPayload: Record<string, unknown> = {
    connection_id: payload.erp_connector_id,
    sync_definition_id: bootstrap.sync_definition_id,
    sync_definition_version_id: bootstrap.sync_definition_version_id,
    dataset_type: datasetType,
    ...toRecord(payload.payload),
  }

  if (payload.retry_of_job_id) {
    requestPayload.retry_of_job_id = payload.retry_of_job_id
  }

  debugErpApiCall("POST", path, requestPayload)
  const response = await apiClient.post<unknown>(path, requestPayload)
  debugErpApiResponse(path, response.data)

  const data = toRecord(response.data)
  const runId = requireId(data)

  return toErpSyncJob(
    {
      ...data,
      id: runId,
      connection_id: payload.erp_connector_id,
      status: data.status,
      created_at: new Date().toISOString(),
    },
    {
      erp_connector_id: payload.erp_connector_id,
      sync_type: payload.sync_type,
      module: payload.module,
    },
  )
}

// TODO: backend not implemented
export const importErpCoa = async (
  erpConnectorId: string,
): Promise<Record<string, unknown>> => {
  void erpConnectorId
  return warnUnsupportedErpFeature()
}

// TODO: backend not implemented
export const mapErpCoa = async (payload: {
  erp_connector_id: string
  mappings: Array<{ erp_account_id: string; internal_account_id: string }>
}): Promise<{ upserted: number }> => {
  void payload
  return warnUnsupportedErpFeature()
}

// TODO: backend not implemented
export const importErpJournals = async (payload: {
  erp_connector_id: string
  transactions?: Array<Record<string, unknown>>
}): Promise<Record<string, unknown>> => {
  void payload
  return warnUnsupportedErpFeature()
}

// TODO: backend not implemented
export const exportErpJournals = async (payload: {
  erp_connector_id: string
  journal_ids?: string[]
}): Promise<Record<string, unknown>> => {
  void payload
  return warnUnsupportedErpFeature()
}

// TODO: backend not implemented
export const syncErpVendors = async (payload: {
  erp_connector_id: string
  rows?: Array<Record<string, unknown>>
}): Promise<Record<string, unknown>> => {
  void payload
  return warnUnsupportedErpFeature()
}

// TODO: backend not implemented
export const syncErpCustomers = async (payload: {
  erp_connector_id: string
  rows?: Array<Record<string, unknown>>
}): Promise<Record<string, unknown>> => {
  void payload
  return warnUnsupportedErpFeature()
}
