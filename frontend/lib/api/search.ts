import apiClient from "@/lib/api/client"
import type { SearchResultRow } from "@/lib/types/search"

export const searchGlobal = async (params?: {
  q?: string
  types?: string[]
  limit?: number
}): Promise<SearchResultRow[]> => {
  const search = new URLSearchParams()
  search.set("q", params?.q ?? "")
  if (params?.types && params.types.length > 0) {
    search.set("types", params.types.join(","))
  }
  search.set("limit", String(params?.limit ?? 10))
  const response = await apiClient.get<SearchResultRow[]>(
    `/api/v1/search?${search.toString()}`,
  )
  return response.data
}

export const queueTenantReindex = async (): Promise<{
  task_id: string
  status: string
  counts: Record<string, number>
}> => {
  const response = await apiClient.post<{
    task_id: string
    status: string
    counts: Record<string, number>
  }>("/api/v1/search/reindex")
  return response.data
}

