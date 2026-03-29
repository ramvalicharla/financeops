import apiClient from "@/lib/api/client"
import type {
  PaginatedResult,
  PartnerCommissionRow,
  PartnerDashboard,
  PartnerProfile,
  ReferralTrackingRow,
} from "@/lib/types/partner"

export const registerPartner = async (payload: {
  partner_tier: "referral" | "reseller" | "technology"
  company_name: string
  contact_email: string
  website_url?: string
}): Promise<PartnerProfile> => {
  const response = await apiClient.post<PartnerProfile>("/api/v1/partner/register", payload)
  return response.data
}

export const getPartnerDashboard = async (): Promise<PartnerDashboard> => {
  const response = await apiClient.get<PartnerDashboard>("/api/v1/partner/dashboard")
  return response.data
}

export const listPartnerReferrals = async (params?: {
  limit?: number
  offset?: number
}): Promise<PaginatedResult<ReferralTrackingRow>> => {
  const search = new URLSearchParams()
  search.set("limit", String(params?.limit ?? 20))
  search.set("offset", String(params?.offset ?? 0))
  const response = await apiClient.get<PaginatedResult<ReferralTrackingRow>>(
    `/api/v1/partner/referrals?${search.toString()}`,
  )
  return response.data
}

export const listPartnerCommissions = async (params?: {
  limit?: number
  offset?: number
}): Promise<PaginatedResult<PartnerCommissionRow>> => {
  const search = new URLSearchParams()
  search.set("limit", String(params?.limit ?? 20))
  search.set("offset", String(params?.offset ?? 0))
  const response = await apiClient.get<PaginatedResult<PartnerCommissionRow>>(
    `/api/v1/partner/commissions?${search.toString()}`,
  )
  return response.data
}

export const trackPartnerReferral = async (payload: {
  partner_code: string
  referral_email?: string
}): Promise<{ tracked: boolean; referral_code: string }> => {
  const response = await apiClient.post<{ tracked: boolean; referral_code: string }>(
    "/api/v1/partner/track",
    payload,
  )
  return response.data
}

export const listPartnerApplications = async (params?: {
  limit?: number
  offset?: number
}): Promise<PaginatedResult<PartnerProfile>> => {
  const search = new URLSearchParams()
  search.set("limit", String(params?.limit ?? 50))
  search.set("offset", String(params?.offset ?? 0))
  const response = await apiClient.get<PaginatedResult<PartnerProfile>>(
    `/api/v1/partner/admin/applications?${search.toString()}`,
  )
  return response.data
}

export const approvePartner = async (partnerId: string): Promise<PartnerProfile> => {
  const response = await apiClient.post<PartnerProfile>(`/api/v1/partner/admin/${partnerId}/approve`)
  return response.data
}

export const getPartnerAdminStats = async (): Promise<{
  total_partners: number
  pending_applications: number
  total_commissions: string
  total_conversions: number
}> => {
  const response = await apiClient.get<{
    total_partners: number
    pending_applications: number
    total_commissions: string
    total_conversions: number
  }>("/api/v1/partner/admin/stats")
  return response.data
}

