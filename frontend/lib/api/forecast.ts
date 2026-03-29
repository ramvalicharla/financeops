import apiClient from "@/lib/api/client"
import type {
  ForecastAssumption,
  ForecastRun,
  ForecastRunDetail,
  ForecastVsBudgetPayload,
  PaginatedResult,
} from "@/lib/types/forecast"

export const createForecastRun = async (payload: {
  run_name: string
  forecast_type: "rolling_12" | "annual" | "quarterly"
  base_period: string
  horizon_months: number
}): Promise<{ run: ForecastRun; assumptions: ForecastAssumption[] }> => {
  const response = await apiClient.post<{ run: ForecastRun; assumptions: ForecastAssumption[] }>(
    "/api/v1/forecast",
    payload,
  )
  return response.data
}

export const listForecastRuns = async (params?: {
  forecast_type?: string
  status?: string
  limit?: number
  offset?: number
}): Promise<PaginatedResult<ForecastRun>> => {
  const search = new URLSearchParams()
  if (params?.forecast_type) search.set("forecast_type", params.forecast_type)
  if (params?.status) search.set("status", params.status)
  if (params?.limit !== undefined) search.set("limit", String(params.limit))
  if (params?.offset !== undefined) search.set("offset", String(params.offset))
  const query = search.toString()
  const response = await apiClient.get<PaginatedResult<ForecastRun>>(
    `/api/v1/forecast${query ? `?${query}` : ""}`,
  )
  return response.data
}

export const getForecastRun = async (runId: string): Promise<ForecastRunDetail> => {
  const response = await apiClient.get<ForecastRunDetail>(`/api/v1/forecast/${runId}`)
  return response.data
}

export const updateForecastAssumption = async (
  runId: string,
  key: string,
  payload: { value: string; basis?: string },
): Promise<{ assumption: ForecastAssumption; line_items_total: number }> => {
  const response = await apiClient.patch<{ assumption: ForecastAssumption; line_items_total: number }>(
    `/api/v1/forecast/${runId}/assumptions/${encodeURIComponent(key)}`,
    payload,
  )
  return response.data
}

export const computeForecast = async (runId: string): Promise<{ line_items_created: number }> => {
  const response = await apiClient.post<{ line_items_created: number }>(`/api/v1/forecast/${runId}/compute`)
  return response.data
}

export const publishForecast = async (runId: string): Promise<ForecastRun> => {
  const response = await apiClient.post<ForecastRun>(`/api/v1/forecast/${runId}/publish`)
  return response.data
}

export const getForecastVsBudget = async (
  runId: string,
  fiscalYear: number,
): Promise<ForecastVsBudgetPayload> => {
  const response = await apiClient.get<ForecastVsBudgetPayload>(
    `/api/v1/forecast/${runId}/vs-budget?fiscal_year=${fiscalYear}`,
  )
  return response.data
}

export const exportForecast = async (runId: string): Promise<Blob> => {
  const response = await apiClient.get(`/api/v1/forecast/${runId}/export`, {
    responseType: "blob",
  })
  return response.data as Blob
}

