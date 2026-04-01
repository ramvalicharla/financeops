import apiClient from "@/lib/api/client"

type QueryPrimitive = string | number | undefined

const buildQuery = (params: Record<string, QueryPrimitive>) => {
  const query = new URLSearchParams()
  for (const [key, value] of Object.entries(params)) {
    if (value === undefined || value === "") continue
    query.set(key, String(value))
  }
  const value = query.toString()
  return value ? `?${value}` : ""
}

export type AiAnomalyRow = {
  id?: string | null
  metric_name: string
  anomaly_type: string
  deviation_value: string
  severity: "LOW" | "MEDIUM" | "HIGH" | "CRITICAL"
  explanation: string
  facts: Record<string, unknown>
  lineage: Record<string, unknown>
  created_at?: string | null
}

export type AiRecommendationRow = {
  id?: string | null
  recommendation_type: string
  severity: "LOW" | "MEDIUM" | "HIGH" | "CRITICAL"
  message: string
  evidence: Record<string, unknown>
  created_at?: string | null
}

export type AiNarrativeResponse = {
  summary: string
  highlights: string[]
  drivers: string[]
  risks: string[]
  actions: string[]
  fact_basis: Record<string, unknown>
  validation_passed: boolean
}

export type AiSuggestion = {
  title: string
  reason: string
  suggested_date: string
  lines: Array<{
    account_code: string
    entry_type: "DEBIT" | "CREDIT"
    amount: string
    memo?: string | null
  }>
  evidence: Record<string, unknown>
}

export type AiAuditSample = {
  journal_id: string
  journal_number: string
  journal_date: string
  total_debit: string
  total_credit: string
  status: string
  source: string
  external_reference_id?: string | null
  risk_score: string
  selection_reason: string
}

export const getAiAnomalies = async (params: {
  org_entity_id?: string
  org_group_id?: string
  from_date?: string
  to_date?: string
  comparison?: string
}) => {
  const query = buildQuery(params)
  const response = await apiClient.get<{ rows: AiAnomalyRow[]; validation: Record<string, unknown> }>(
    `/api/v1/ai/anomalies${query}`,
  )
  return response.data
}

export const getAiVarianceExplanation = async (params: {
  metric_name: string
  org_entity_id?: string
  org_group_id?: string
  from_date?: string
  to_date?: string
  comparison?: string
}) => {
  const query = buildQuery(params)
  const response = await apiClient.get(`/api/v1/ai/explain-variance${query}`)
  return response.data
}

export const getAiRecommendations = async (params: {
  org_entity_id?: string
  org_group_id?: string
  from_date?: string
  to_date?: string
  comparison?: string
}) => {
  const query = buildQuery(params)
  const response = await apiClient.get<{ rows: AiRecommendationRow[]; validation: Record<string, unknown> }>(
    `/api/v1/ai/recommendations${query}`,
  )
  return response.data
}

export const getAiNarrative = async (params: {
  org_entity_id?: string
  org_group_id?: string
  from_date?: string
  to_date?: string
  comparison?: string
}) => {
  const query = buildQuery(params)
  const response = await apiClient.get<AiNarrativeResponse>(`/api/v1/ai/narrative${query}`)
  return response.data
}

export const getAiSuggestions = async (params: {
  org_entity_id?: string
  org_group_id?: string
  from_date?: string
  to_date?: string
}) => {
  const query = buildQuery(params)
  const response = await apiClient.get<{ rows: AiSuggestion[]; validation: Record<string, unknown> }>(
    `/api/v1/ai/suggestions${query}`,
  )
  return response.data
}

export const getAiAuditSamples = async (params: {
  org_entity_id?: string
  org_group_id?: string
  from_date?: string
  to_date?: string
  mode?: "random" | "risk_based"
  sample_size?: number
}) => {
  const query = buildQuery(params)
  const response = await apiClient.get<{
    mode: "random" | "risk_based"
    sample_size: number
    rows: AiAuditSample[]
    fact_basis: Record<string, unknown>
  }>(`/api/v1/ai/audit-samples${query}`)
  return response.data
}

