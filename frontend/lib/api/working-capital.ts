import apiClient from "@/lib/api/client"
import type {
  PaginatedResult,
  WCAPItem,
  WCARItem,
  WCDashboardPayload,
  WCTrendPoint,
} from "@/lib/types/working-capital"

export const fetchWCDashboard = async (period?: string): Promise<WCDashboardPayload> => {
  const query = period ? `?period=${encodeURIComponent(period)}` : ""
  const response = await apiClient.get<WCDashboardPayload>(`/api/v1/working-capital/dashboard${query}`)
  return response.data
}

export const fetchWCAR = async (params: {
  period?: string
  aging_bucket?: string
  limit?: number
  offset?: number
}): Promise<PaginatedResult<WCARItem>> => {
  const search = new URLSearchParams()
  if (params.period) search.set("period", params.period)
  if (params.aging_bucket) search.set("aging_bucket", params.aging_bucket)
  if (params.limit !== undefined) search.set("limit", String(params.limit))
  if (params.offset !== undefined) search.set("offset", String(params.offset))
  const response = await apiClient.get<PaginatedResult<WCARItem>>(
    `/api/v1/working-capital/ar?${search.toString()}`,
  )
  return response.data
}

export const fetchWCAP = async (params: {
  period?: string
  aging_bucket?: string
  discount_only?: boolean
  limit?: number
  offset?: number
}): Promise<PaginatedResult<WCAPItem>> => {
  const search = new URLSearchParams()
  if (params.period) search.set("period", params.period)
  if (params.aging_bucket) search.set("aging_bucket", params.aging_bucket)
  if (params.discount_only !== undefined) search.set("discount_only", params.discount_only ? "true" : "false")
  if (params.limit !== undefined) search.set("limit", String(params.limit))
  if (params.offset !== undefined) search.set("offset", String(params.offset))
  const response = await apiClient.get<PaginatedResult<WCAPItem>>(
    `/api/v1/working-capital/ap?${search.toString()}`,
  )
  return response.data
}

export const fetchWCTrends = async (): Promise<WCTrendPoint[]> => {
  const response = await apiClient.get<WCTrendPoint[]>("/api/v1/working-capital/trends")
  return response.data
}
