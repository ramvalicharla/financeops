import apiClient from "@/lib/api/client"
import type {
  CreateReportDefinitionRequest,
  MetricDefinition,
  ReportDefinitionResponse,
  ReportResultResponse,
  ReportRunResponse,
  UpdateReportDefinitionRequest,
} from "@/lib/types/report-builder"

export const fetchMetrics = async (): Promise<MetricDefinition[]> => {
  const response = await apiClient.get<MetricDefinition[]>("/api/v1/reports/metrics")
  return response.data
}

export const fetchReportDefinitions = async (
  activeOnly = true,
): Promise<ReportDefinitionResponse[]> => {
  const response = await apiClient.get<ReportDefinitionResponse[]>(
    `/api/v1/reports/definitions?active_only=${activeOnly ? "true" : "false"}`,
  )
  return response.data
}

export const createReportDefinition = async (
  body: CreateReportDefinitionRequest,
): Promise<ReportDefinitionResponse> => {
  const response = await apiClient.post<ReportDefinitionResponse>(
    "/api/v1/reports/definitions",
    body,
  )
  return response.data
}

export const updateReportDefinition = async (
  id: string,
  body: UpdateReportDefinitionRequest,
): Promise<ReportDefinitionResponse> => {
  const response = await apiClient.patch<ReportDefinitionResponse>(
    `/api/v1/reports/definitions/${id}`,
    body,
  )
  return response.data
}

export const deleteReportDefinition = async (id: string): Promise<void> => {
  await apiClient.delete(`/api/v1/reports/definitions/${id}`)
}

export const runReport = async (definitionId: string): Promise<ReportRunResponse> => {
  const response = await apiClient.post<ReportRunResponse>("/api/v1/reports/run", {
    definition_id: definitionId,
  })
  return response.data
}

export const fetchReportRuns = async (params?: {
  definition_id?: string
  status?: string
  limit?: number
}): Promise<ReportRunResponse[]> => {
  const search = new URLSearchParams()
  if (params?.definition_id) {
    search.set("definition_id", params.definition_id)
  }
  if (params?.status) {
    search.set("status", params.status)
  }
  if (params?.limit !== undefined) {
    search.set("limit", String(params.limit))
  }
  const query = search.toString()
  const response = await apiClient.get<
    ReportRunResponse[] | { data: ReportRunResponse[] }
  >(`/api/v1/reports/runs${query ? `?${query}` : ""}`)
  return Array.isArray(response.data) ? response.data : response.data.data
}

export const fetchReportRun = async (id: string): Promise<ReportRunResponse> => {
  const response = await apiClient.get<ReportRunResponse>(`/api/v1/reports/runs/${id}`)
  return response.data
}

export const fetchReportResult = async (runId: string): Promise<ReportResultResponse> => {
  const response = await apiClient.get<ReportResultResponse>(
    `/api/v1/reports/runs/${runId}/result`,
  )
  return response.data
}

export const downloadReportResult = async (
  runId: string,
  fmt: "csv" | "excel" | "pdf",
): Promise<Blob> => {
  const response = await apiClient.get<Blob>(
    `/api/v1/reports/runs/${runId}/download/${fmt}`,
    {
      responseType: "blob",
    },
  )
  return response.data
}
