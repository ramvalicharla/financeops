import apiClient from "@/lib/api/client"
import type {
  ComplianceControl,
  ComplianceDashboard,
  ConsentSummary,
  GDPRBreach,
} from "@/lib/types/compliance"

export type PaginatedResponse<T> = {
  data: T[]
  total: number
  limit: number
  offset: number
}

export const getSoc2Dashboard = async (): Promise<ComplianceDashboard> => {
  const response = await apiClient.get<ComplianceDashboard>("/api/v1/compliance/soc2/dashboard")
  return response.data
}

export const evaluateSoc2 = async (): Promise<{ total: number; passed: number; failed: number }> => {
  const response = await apiClient.post<{ total: number; passed: number; failed: number }>(
    "/api/v1/compliance/soc2/evaluate",
  )
  return response.data
}

export const getSoc2Evidence = async (): Promise<Record<string, unknown>> => {
  const response = await apiClient.get<Record<string, unknown>>("/api/v1/compliance/soc2/evidence")
  return response.data
}

export const listSoc2Controls = async (params: {
  status?: string
  rag_status?: string
  category?: string
  limit?: number
  offset?: number
}): Promise<PaginatedResponse<ComplianceControl>> => {
  const search = new URLSearchParams()
  if (params.status) search.set("status", params.status)
  if (params.rag_status) search.set("rag_status", params.rag_status)
  if (params.category) search.set("category", params.category)
  search.set("limit", String(params.limit ?? 50))
  search.set("offset", String(params.offset ?? 0))
  const response = await apiClient.get<PaginatedResponse<ComplianceControl>>(
    `/api/v1/compliance/soc2/controls?${search.toString()}`,
  )
  return response.data
}

export const updateSoc2ControlStatus = async (
  controlId: string,
  payload: { status: string; notes?: string },
): Promise<ComplianceControl> => {
  const response = await apiClient.patch<ComplianceControl>(
    `/api/v1/compliance/soc2/controls/${controlId}/status`,
    payload,
  )
  return response.data
}

export const getIsoDashboard = async (): Promise<ComplianceDashboard> => {
  const response = await apiClient.get<ComplianceDashboard>("/api/v1/compliance/iso27001/dashboard")
  return response.data
}

export const evaluateIso = async (): Promise<{ total: number; passed: number; failed: number }> => {
  const response = await apiClient.post<{ total: number; passed: number; failed: number }>(
    "/api/v1/compliance/iso27001/evaluate",
  )
  return response.data
}

export const getIsoEvidence = async (): Promise<Record<string, unknown>> => {
  const response = await apiClient.get<Record<string, unknown>>("/api/v1/compliance/iso27001/evidence")
  return response.data
}

export const listIsoControls = async (params: {
  status?: string
  rag_status?: string
  category?: string
  limit?: number
  offset?: number
}): Promise<PaginatedResponse<ComplianceControl>> => {
  const search = new URLSearchParams()
  if (params.status) search.set("status", params.status)
  if (params.rag_status) search.set("rag_status", params.rag_status)
  if (params.category) search.set("category", params.category)
  search.set("limit", String(params.limit ?? 50))
  search.set("offset", String(params.offset ?? 0))
  const response = await apiClient.get<PaginatedResponse<ComplianceControl>>(
    `/api/v1/compliance/iso27001/controls?${search.toString()}`,
  )
  return response.data
}

export const updateIsoControlStatus = async (
  controlId: string,
  payload: { status: string; notes?: string },
): Promise<ComplianceControl> => {
  const response = await apiClient.patch<ComplianceControl>(
    `/api/v1/compliance/iso27001/controls/${controlId}/status`,
    payload,
  )
  return response.data
}

export const exportOwnData = async (): Promise<Record<string, unknown>> => {
  const response = await apiClient.post<Record<string, unknown>>("/api/v1/compliance/gdpr/export", {})
  return response.data
}

export const recordConsent = async (payload: {
  consent_type: string
  granted: boolean
  lawful_basis?: string
}): Promise<Record<string, unknown>> => {
  const response = await apiClient.post<Record<string, unknown>>(
    "/api/v1/compliance/gdpr/consent",
    payload,
  )
  return response.data
}

export const listOwnConsent = async (): Promise<Array<Record<string, unknown>>> => {
  const response = await apiClient.get<Array<Record<string, unknown>>>("/api/v1/compliance/gdpr/consent")
  return response.data
}

export const getConsentSummary = async (): Promise<ConsentSummary> => {
  const response = await apiClient.get<ConsentSummary>("/api/v1/compliance/gdpr/consent/summary")
  return response.data
}

export const createBreach = async (payload: {
  breach_type: string
  description: string
  affected_user_count: number
  affected_data_types: string[]
  discovered_at: string
  severity: "low" | "medium" | "high" | "critical"
  status?: "open" | "reported" | "closed"
  remediation_notes?: string
}): Promise<GDPRBreach> => {
  const response = await apiClient.post<GDPRBreach>("/api/v1/compliance/gdpr/breach", payload)
  return response.data
}

export const listBreaches = async (params?: {
  limit?: number
  offset?: number
}): Promise<PaginatedResponse<GDPRBreach>> => {
  const search = new URLSearchParams()
  search.set("limit", String(params?.limit ?? 20))
  search.set("offset", String(params?.offset ?? 0))
  const response = await apiClient.get<PaginatedResponse<GDPRBreach>>(
    `/api/v1/compliance/gdpr/breaches?${search.toString()}`,
  )
  return response.data
}

