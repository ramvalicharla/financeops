import apiClient from "@/lib/api/client"
import type {
  PPAAllocation,
  PPAEngagement,
  PPAIntangible,
  PPAIntangibleSuggestion,
  PPAReport,
  PaginatedResult,
} from "@/lib/types/ppa"

export const createPPAEngagement = async (payload: {
  engagement_name: string
  target_company_name: string
  acquisition_date: string
  purchase_price: string
  purchase_price_currency: string
  accounting_standard: "IFRS3" | "ASC805" | "INDAS103"
}): Promise<PPAEngagement> => {
  const response = await apiClient.post<PPAEngagement>("/api/v1/advisory/ppa/engagements", payload)
  return response.data
}

export const listPPAEngagements = async (params?: {
  status?: string
  limit?: number
  offset?: number
}): Promise<PaginatedResult<PPAEngagement>> => {
  const search = new URLSearchParams()
  if (params?.status) search.set("status", params.status)
  if (params?.limit !== undefined) search.set("limit", String(params.limit))
  if (params?.offset !== undefined) search.set("offset", String(params.offset))
  const query = search.toString()
  const response = await apiClient.get<PaginatedResult<PPAEngagement>>(
    `/api/v1/advisory/ppa/engagements${query ? `?${query}` : ""}`,
  )
  return response.data
}

export const getPPAEngagement = async (
  engagementId: string,
): Promise<{
  engagement: PPAEngagement
  allocation: PPAAllocation | null
  intangibles: PPAIntangible[]
}> => {
  const response = await apiClient.get<{
    engagement: PPAEngagement
    allocation: PPAAllocation | null
    intangibles: PPAIntangible[]
  }>(`/api/v1/advisory/ppa/engagements/${engagementId}`)
  return response.data
}

export const identifyPPAIntangibles = async (
  engagementId: string,
): Promise<PPAIntangibleSuggestion[]> => {
  const response = await apiClient.post<{ intangibles: PPAIntangibleSuggestion[] }>(
    `/api/v1/advisory/ppa/engagements/${engagementId}/identify-intangibles`,
  )
  return response.data.intangibles
}

export const runPPAEngagement = async (
  engagementId: string,
  payload: {
    intangibles: Array<{
      name: string
      category: string
      valuation_method: string
      useful_life_years: string
      assumptions: Record<string, string>
      amortisation_method?: string
      tax_basis?: string
      applicable_tax_rate?: string
    }>
  },
): Promise<PPAAllocation> => {
  const response = await apiClient.post<PPAAllocation>(
    `/api/v1/advisory/ppa/engagements/${engagementId}/run`,
    payload,
  )
  return response.data
}

export const getPPAReport = async (engagementId: string): Promise<PPAReport> => {
  const response = await apiClient.get<PPAReport>(`/api/v1/advisory/ppa/engagements/${engagementId}/report`)
  return response.data
}

export const exportPPAReport = async (engagementId: string): Promise<Blob> => {
  const response = await apiClient.get(`/api/v1/advisory/ppa/engagements/${engagementId}/export`, {
    responseType: "blob",
  })
  return response.data as Blob
}
