import apiClient from "@/lib/api/client"
import type {
  MarketplaceContributor,
  MarketplacePayout,
  MarketplacePurchase,
  MarketplaceRating,
  MarketplaceTemplate,
  PaginatedResult,
} from "@/lib/types/marketplace"

export const listMarketplaceTemplates = async (params?: {
  template_type?: string
  industry?: string
  is_free?: boolean
  sort_by?: string
  limit?: number
  offset?: number
}): Promise<PaginatedResult<MarketplaceTemplate>> => {
  const search = new URLSearchParams()
  if (params?.template_type) search.set("template_type", params.template_type)
  if (params?.industry) search.set("industry", params.industry)
  if (params?.is_free !== undefined) search.set("is_free", String(params.is_free))
  if (params?.sort_by) search.set("sort_by", params.sort_by)
  search.set("limit", String(params?.limit ?? 20))
  search.set("offset", String(params?.offset ?? 0))
  const response = await apiClient.get<PaginatedResult<MarketplaceTemplate>>(
    `/api/v1/marketplace/templates?${search.toString()}`,
  )
  return response.data
}

export const getMarketplaceTemplate = async (
  templateId: string,
): Promise<{ template: MarketplaceTemplate; reviews: MarketplaceRating[] }> => {
  const response = await apiClient.get<{
    template: MarketplaceTemplate
    reviews: MarketplaceRating[]
  }>(`/api/v1/marketplace/templates/${templateId}`)
  return response.data
}

export const purchaseMarketplaceTemplate = async (
  templateId: string,
): Promise<{
  purchase: MarketplacePurchase
  template_data: Record<string, unknown>
}> => {
  const response = await apiClient.post<{
    purchase: MarketplacePurchase
    template_data: Record<string, unknown>
  }>(`/api/v1/marketplace/templates/${templateId}/purchase`)
  return response.data
}

export const rateMarketplaceTemplate = async (
  templateId: string,
  payload: { rating: number; review_text?: string },
): Promise<MarketplaceRating> => {
  const response = await apiClient.post<MarketplaceRating>(
    `/api/v1/marketplace/templates/${templateId}/rate`,
    payload,
  )
  return response.data
}

export const registerMarketplaceContributor = async (payload: {
  display_name: string
  bio?: string
}): Promise<MarketplaceContributor> => {
  const response = await apiClient.post<MarketplaceContributor>(
    "/api/v1/marketplace/contributor/register",
    payload,
  )
  return response.data
}

export const getMarketplaceContributorDashboard = async (): Promise<{
  contributor: MarketplaceContributor
  templates: MarketplaceTemplate[]
  earnings_this_month: string
  earnings_total: string
  top_template: MarketplaceTemplate | null
  recent_purchases: MarketplacePurchase[]
  payout_history: MarketplacePayout[]
}> => {
  const response = await apiClient.get<{
    contributor: MarketplaceContributor
    templates: MarketplaceTemplate[]
    earnings_this_month: string
    earnings_total: string
    top_template: MarketplaceTemplate | null
    recent_purchases: MarketplacePurchase[]
    payout_history: MarketplacePayout[]
  }>("/api/v1/marketplace/contributor/dashboard")
  return response.data
}

export const submitMarketplaceTemplate = async (payload: {
  title: string
  description: string
  template_type: string
  price_credits: number
  template_data: Record<string, unknown>
  industry?: string
  tags?: string[]
}): Promise<MarketplaceTemplate> => {
  const response = await apiClient.post<MarketplaceTemplate>(
    "/api/v1/marketplace/contributor/templates",
    payload,
  )
  return response.data
}

export const updateMarketplaceTemplate = async (
  templateId: string,
  payload: Partial<{
    title: string
    description: string
    template_type: string
    price_credits: number
    template_data: Record<string, unknown>
    industry: string
    tags: string[]
  }>,
): Promise<MarketplaceTemplate> => {
  const response = await apiClient.patch<MarketplaceTemplate>(
    `/api/v1/marketplace/contributor/templates/${templateId}`,
    payload,
  )
  return response.data
}

export const listMarketplacePending = async (params?: {
  limit?: number
  offset?: number
}): Promise<PaginatedResult<MarketplaceTemplate>> => {
  const search = new URLSearchParams()
  search.set("limit", String(params?.limit ?? 50))
  search.set("offset", String(params?.offset ?? 0))
  const response = await apiClient.get<PaginatedResult<MarketplaceTemplate>>(
    `/api/v1/marketplace/admin/pending?${search.toString()}`,
  )
  return response.data
}

export const reviewMarketplaceTemplate = async (
  templateId: string,
  payload: { action: "approve" | "reject"; review_notes?: string },
): Promise<MarketplaceTemplate> => {
  const response = await apiClient.post<MarketplaceTemplate>(
    `/api/v1/marketplace/admin/templates/${templateId}/review`,
    payload,
  )
  return response.data
}

export const processMarketplacePayouts = async (): Promise<{
  count: number
  payouts: MarketplacePayout[]
}> => {
  const response = await apiClient.post<{ count: number; payouts: MarketplacePayout[] }>(
    "/api/v1/marketplace/admin/payouts/process",
  )
  return response.data
}

export const getMarketplaceStats = async (): Promise<{
  total_templates: number
  published_templates: number
  total_revenue_credits: number
  top_contributors: MarketplaceContributor[]
}> => {
  const response = await apiClient.get<{
    total_templates: number
    published_templates: number
    total_revenue_credits: number
    top_contributors: MarketplaceContributor[]
  }>("/api/v1/marketplace/admin/stats")
  return response.data
}

