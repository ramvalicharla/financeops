import apiClient from "@/lib/api/client"
import type {
  MADocument,
  MADDItem,
  MADDTrackerSummary,
  MAValuation,
  MAWorkspace,
  MAWorkspaceMember,
  PaginatedResult,
} from "@/lib/types/ma"

export const createMAWorkspace = async (payload: {
  workspace_name: string
  deal_codename: string
  deal_type: string
  target_company_name: string
  indicative_deal_value?: string
}): Promise<MAWorkspace> => {
  const response = await apiClient.post<MAWorkspace>("/api/v1/advisory/ma/workspaces", payload)
  return response.data
}

export const listMAWorkspaces = async (params?: {
  deal_status?: string
  limit?: number
  offset?: number
}): Promise<PaginatedResult<MAWorkspace>> => {
  const search = new URLSearchParams()
  if (params?.deal_status) search.set("deal_status", params.deal_status)
  if (params?.limit !== undefined) search.set("limit", String(params.limit))
  if (params?.offset !== undefined) search.set("offset", String(params.offset))
  const query = search.toString()
  const response = await apiClient.get<PaginatedResult<MAWorkspace>>(
    `/api/v1/advisory/ma/workspaces${query ? `?${query}` : ""}`,
  )
  return response.data
}

export const getMAWorkspace = async (
  workspaceId: string,
): Promise<{
  workspace: MAWorkspace
  members: MAWorkspaceMember[]
  dd_summary: MADDTrackerSummary
}> => {
  const response = await apiClient.get<{
    workspace: MAWorkspace
    members: MAWorkspaceMember[]
    dd_summary: MADDTrackerSummary
  }>(`/api/v1/advisory/ma/workspaces/${workspaceId}`)
  return response.data
}

export const updateMAWorkspace = async (
  workspaceId: string,
  payload: {
    deal_status?: string
    indicative_deal_value?: string
  },
): Promise<MAWorkspace> => {
  const response = await apiClient.patch<MAWorkspace>(`/api/v1/advisory/ma/workspaces/${workspaceId}`, payload)
  return response.data
}

export const listMAValuations = async (
  workspaceId: string,
  params?: { limit?: number; offset?: number },
): Promise<PaginatedResult<MAValuation>> => {
  const search = new URLSearchParams()
  if (params?.limit !== undefined) search.set("limit", String(params.limit))
  if (params?.offset !== undefined) search.set("offset", String(params.offset))
  const query = search.toString()
  const response = await apiClient.get<PaginatedResult<MAValuation>>(
    `/api/v1/advisory/ma/workspaces/${workspaceId}/valuations${query ? `?${query}` : ""}`,
  )
  return response.data
}

export const createMAValuation = async (
  workspaceId: string,
  payload: {
    valuation_name: string
    valuation_method: string
    assumptions: Record<string, string>
  },
): Promise<MAValuation> => {
  const response = await apiClient.post<MAValuation>(
    `/api/v1/advisory/ma/workspaces/${workspaceId}/valuations`,
    payload,
  )
  return response.data
}

export const getMADDTracker = async (
  workspaceId: string,
): Promise<{
  summary: MADDTrackerSummary
  items: MADDItem[]
}> => {
  const response = await apiClient.get<{
    summary: MADDTrackerSummary
    items: MADDItem[]
  }>(`/api/v1/advisory/ma/workspaces/${workspaceId}/dd`)
  return response.data
}

export const createMADDItem = async (
  workspaceId: string,
  payload: {
    category: string
    item_name: string
    description?: string
    priority?: string
    assigned_to?: string
    due_date?: string
  },
): Promise<MADDItem> => {
  const response = await apiClient.post<MADDItem>(`/api/v1/advisory/ma/workspaces/${workspaceId}/dd`, payload)
  return response.data
}

export const updateMADDItem = async (
  workspaceId: string,
  itemId: string,
  payload: {
    status?: string
    response_notes?: string
  },
): Promise<MADDItem> => {
  const response = await apiClient.patch<MADDItem>(
    `/api/v1/advisory/ma/workspaces/${workspaceId}/dd/${itemId}`,
    payload,
  )
  return response.data
}

export const listMADocuments = async (
  workspaceId: string,
  params?: { document_type?: string; limit?: number; offset?: number },
): Promise<PaginatedResult<MADocument>> => {
  const search = new URLSearchParams()
  if (params?.document_type) search.set("document_type", params.document_type)
  if (params?.limit !== undefined) search.set("limit", String(params.limit))
  if (params?.offset !== undefined) search.set("offset", String(params.offset))
  const query = search.toString()
  const response = await apiClient.get<PaginatedResult<MADocument>>(
    `/api/v1/advisory/ma/workspaces/${workspaceId}/documents${query ? `?${query}` : ""}`,
  )
  return response.data
}

export const registerMADocument = async (
  workspaceId: string,
  payload: {
    document_name: string
    document_type: string
    file_url?: string
    file_size_bytes?: number
    is_confidential?: boolean
  },
): Promise<MADocument> => {
  const response = await apiClient.post<MADocument>(
    `/api/v1/advisory/ma/workspaces/${workspaceId}/documents`,
    payload,
  )
  return response.data
}
