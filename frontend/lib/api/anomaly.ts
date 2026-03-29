import apiClient, { parseWithSchema } from "@/lib/api/client"
import { AnomalySchema } from "@/lib/schemas/anomaly"
import type {
  AnomalyAlert,
  AnomalyStatus,
  AnomalyThreshold,
  UpdateAnomalyStatusRequest,
  UpdateAnomalyThresholdRequest,
  UpdateAnomalyThresholdResponse,
} from "@/lib/types/anomaly"

export const fetchAnomalyAlerts = async (params?: {
  severity?: string
  category?: string
  status?: AnomalyStatus | "ALL"
  limit?: number
}): Promise<AnomalyAlert[]> => {
  const search = new URLSearchParams()
  if (params?.severity && params.severity !== "ALL") {
    search.set("severity", params.severity.toLowerCase())
  }
  if (params?.category && params.category !== "ALL") {
    search.set("category", params.category)
  }
  if (params?.status) {
    search.set("status", params.status)
  }
  if (params?.limit !== undefined) {
    search.set("limit", String(params.limit))
  }
  const query = search.toString()
  const endpoint = `/api/v1/anomalies/${query ? `?${query}` : ""}`
  const response = await apiClient.get<unknown>(endpoint)
  const raw = response.data
  const items = Array.isArray(raw) ? raw : (raw as { data: unknown[] }).data
  return items.map((item) => parseWithSchema(endpoint, item, AnomalySchema)) as unknown as AnomalyAlert[]
}

export const fetchAnomalyAlert = async (alertId: string): Promise<AnomalyAlert> => {
  const endpoint = `/api/v1/anomalies/${alertId}`
  const response = await apiClient.get<unknown>(endpoint)
  return parseWithSchema(endpoint, response.data, AnomalySchema) as unknown as AnomalyAlert
}

export const updateAnomalyStatus = async (
  alertId: string,
  body: UpdateAnomalyStatusRequest,
): Promise<AnomalyAlert> => {
  const response = await apiClient.patch<AnomalyAlert>(
    `/api/v1/anomalies/${alertId}/status`,
    body,
  )
  return response.data
}

export const fetchAnomalyThresholds = async (): Promise<AnomalyThreshold[]> => {
  const response = await apiClient.get<AnomalyThreshold[] | { data: AnomalyThreshold[] }>(
    "/api/v1/anomalies/thresholds",
  )
  return Array.isArray(response.data) ? response.data : response.data.data
}

export const updateAnomalyThreshold = async (
  ruleCode: string,
  body: UpdateAnomalyThresholdRequest,
): Promise<UpdateAnomalyThresholdResponse> => {
  const response = await apiClient.put<UpdateAnomalyThresholdResponse>(
    `/api/v1/anomalies/thresholds/${ruleCode}`,
    body,
  )
  return response.data
}
