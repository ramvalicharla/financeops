import apiClient from "@/lib/api/client"
import type {
  BudgetLineItem,
  BudgetVersion,
  BudgetVsActualPayload,
  PaginatedResult,
} from "@/lib/types/budget"

export const createBudgetVersion = async (payload: {
  fiscal_year: number
  version_name: string
  copy_from_version_id?: string
}): Promise<BudgetVersion> => {
  const response = await apiClient.post<BudgetVersion>("/api/v1/budget/versions", payload)
  return response.data
}

export const listBudgetVersions = async (params: {
  fiscal_year?: number
  limit?: number
  offset?: number
}): Promise<PaginatedResult<BudgetVersion>> => {
  const search = new URLSearchParams()
  if (params.fiscal_year !== undefined) search.set("fiscal_year", String(params.fiscal_year))
  if (params.limit !== undefined) search.set("limit", String(params.limit))
  if (params.offset !== undefined) search.set("offset", String(params.offset))
  const query = search.toString()
  const response = await apiClient.get<PaginatedResult<BudgetVersion>>(
    `/api/v1/budget/versions${query ? `?${query}` : ""}`,
  )
  return response.data
}

export const getBudgetVersion = async (
  versionId: string,
): Promise<BudgetVersion & { lines: BudgetLineItem[] }> => {
  const response = await apiClient.get<BudgetVersion & { lines: BudgetLineItem[] }>(
    `/api/v1/budget/versions/${versionId}`,
  )
  return response.data
}

export const addBudgetLine = async (
  versionId: string,
  payload: {
    mis_line_item: string
    mis_category: string
    monthly_values: string[]
    basis?: string
    entity_id?: string
  },
): Promise<BudgetLineItem> => {
  const response = await apiClient.post<BudgetLineItem>(
    `/api/v1/budget/versions/${versionId}/lines`,
    payload,
  )
  return response.data
}

export const approveBudgetVersion = async (versionId: string): Promise<BudgetVersion> => {
  const response = await apiClient.post<BudgetVersion>(`/api/v1/budget/versions/${versionId}/approve`)
  return response.data
}

export const getBudgetVsActual = async (params: {
  fiscal_year: number
  period: string
  version_id?: string
  entity_id?: string
}): Promise<BudgetVsActualPayload> => {
  const search = new URLSearchParams()
  search.set("fiscal_year", String(params.fiscal_year))
  search.set("period", params.period)
  if (params.version_id) search.set("version_id", params.version_id)
  if (params.entity_id) search.set("entity_id", params.entity_id)
  const response = await apiClient.get<BudgetVsActualPayload>(
    `/api/v1/budget/vs-actual?${search.toString()}`,
  )
  return response.data
}

export const exportBudgetVsActual = async (params: {
  fiscal_year: number
  period: string
  version_id?: string
}): Promise<Blob> => {
  const search = new URLSearchParams()
  search.set("fiscal_year", String(params.fiscal_year))
  search.set("period", params.period)
  if (params.version_id) search.set("version_id", params.version_id)
  const response = await apiClient.get(
    `/api/v1/budget/vs-actual/export?${search.toString()}`,
    { responseType: "blob" },
  )
  return response.data as Blob
}

