import apiClient from "@/lib/api/client"
import type { FDDEngagement, FDDFinding, FDDReport, FDDSection, PaginatedResult } from "@/lib/types/fdd"

export const createFDDEngagement = async (payload: {
  engagement_name: string
  target_company_name: string
  analysis_period_start: string
  analysis_period_end: string
  sections_requested: string[]
}): Promise<FDDEngagement> => {
  const response = await apiClient.post<FDDEngagement>("/api/v1/advisory/fdd/engagements", payload)
  return response.data
}

export const listFDDEngagements = async (params?: {
  status?: string
  limit?: number
  offset?: number
}): Promise<PaginatedResult<FDDEngagement>> => {
  const search = new URLSearchParams()
  if (params?.status) search.set("status", params.status)
  if (params?.limit !== undefined) search.set("limit", String(params.limit))
  if (params?.offset !== undefined) search.set("offset", String(params.offset))
  const query = search.toString()
  const response = await apiClient.get<PaginatedResult<FDDEngagement>>(
    `/api/v1/advisory/fdd/engagements${query ? `?${query}` : ""}`,
  )
  return response.data
}

export const getFDDEngagement = async (
  engagementId: string,
): Promise<{
  engagement: FDDEngagement
  sections: FDDSection[]
  findings: FDDFinding[]
}> => {
  const response = await apiClient.get<{
    engagement: FDDEngagement
    sections: FDDSection[]
    findings: FDDFinding[]
  }>(`/api/v1/advisory/fdd/engagements/${engagementId}`)
  return response.data
}

export const runFDDEngagement = async (
  engagementId: string,
): Promise<{ task_id: string; status: string }> => {
  const response = await apiClient.post<{ task_id: string; status: string }>(
    `/api/v1/advisory/fdd/engagements/${engagementId}/run`,
  )
  return response.data
}

export const getFDDReport = async (engagementId: string): Promise<FDDReport> => {
  const response = await apiClient.get<FDDReport>(`/api/v1/advisory/fdd/engagements/${engagementId}/report`)
  return response.data
}

export const exportFDDReport = async (engagementId: string): Promise<Blob> => {
  const response = await apiClient.get(`/api/v1/advisory/fdd/engagements/${engagementId}/export`, {
    responseType: "blob",
  })
  return response.data as Blob
}
