import apiClient from "@/lib/api/client"
import type { PaginatedResult, WhiteLabelAuditLogRow, WhiteLabelConfig } from "@/lib/types/white-label"

export const getWhiteLabelConfig = async (): Promise<WhiteLabelConfig> => {
  const response = await apiClient.get<WhiteLabelConfig>("/api/v1/white-label/config")
  return response.data
}

export const updateWhiteLabelConfig = async (
  payload: Partial<{
    custom_domain: string
    brand_name: string
    logo_url: string
    favicon_url: string
    primary_colour: string
    secondary_colour: string
    font_family: string
    hide_powered_by: boolean
    custom_css: string
    support_email: string
    support_url: string
  }>,
): Promise<WhiteLabelConfig> => {
  const response = await apiClient.patch<WhiteLabelConfig>("/api/v1/white-label/config", payload)
  return response.data
}

export const initiateWhiteLabelDomainVerification = async (
  customDomain: string,
): Promise<{
  domain: string
  verification_token: string
  txt_record_name: string
  txt_record_value: string
  instructions: string
}> => {
  const response = await apiClient.post<{
    domain: string
    verification_token: string
    txt_record_name: string
    txt_record_value: string
    instructions: string
  }>("/api/v1/white-label/domain/verify-initiate", { custom_domain: customDomain })
  return response.data
}

export const checkWhiteLabelDomainVerification = async (): Promise<{
  verified: boolean
  domain: string | null
}> => {
  const response = await apiClient.post<{ verified: boolean; domain: string | null }>(
    "/api/v1/white-label/domain/verify-check",
  )
  return response.data
}

export const listWhiteLabelAuditLog = async (params?: {
  limit?: number
  offset?: number
}): Promise<PaginatedResult<WhiteLabelAuditLogRow>> => {
  const search = new URLSearchParams()
  search.set("limit", String(params?.limit ?? 20))
  search.set("offset", String(params?.offset ?? 0))
  const response = await apiClient.get<PaginatedResult<WhiteLabelAuditLogRow>>(
    `/api/v1/white-label/audit-log?${search.toString()}`,
  )
  return response.data
}

export const listWhiteLabelAdminConfigs = async (params?: {
  limit?: number
  offset?: number
}): Promise<PaginatedResult<WhiteLabelConfig>> => {
  const search = new URLSearchParams()
  search.set("limit", String(params?.limit ?? 50))
  search.set("offset", String(params?.offset ?? 0))
  const response = await apiClient.get<PaginatedResult<WhiteLabelConfig>>(
    `/api/v1/white-label/admin/all?${search.toString()}`,
  )
  return response.data
}

export const enableWhiteLabelTenant = async (tenantId: string): Promise<WhiteLabelConfig> => {
  const response = await apiClient.post<WhiteLabelConfig>(`/api/v1/white-label/admin/${tenantId}/enable`)
  return response.data
}

export const resolveWhiteLabelDomain = async (domain: string): Promise<WhiteLabelConfig> => {
  const response = await apiClient.get<WhiteLabelConfig>(`/api/v1/white-label/resolve/${domain}`)
  return response.data
}

