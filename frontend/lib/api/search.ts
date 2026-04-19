import apiClient from "@/lib/api/client"
import type { UnifiedSearchResponse } from "@/lib/types/search"

export const searchGlobal = async (params?: {
  q?: string
  module?: string
  limit?: number
  offset?: number
}): Promise<UnifiedSearchResponse> => {
  const search = new URLSearchParams()
  if (params?.q) search.set("q", params.q)
  if (params?.module && params.module !== "all") search.set("module", params.module)
  if (params?.limit) search.set("limit", String(params.limit))
  if (params?.offset !== undefined) search.set("offset", String(params.offset))

  const response = await apiClient.get<UnifiedSearchResponse>(
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

