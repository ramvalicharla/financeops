import apiClient from "@/lib/api/client"

export type FxRateType = "SPOT" | "AVERAGE" | "CLOSING"

export interface FxRateRecord {
  id: string
  tenant_id: string | null
  from_currency: string
  to_currency: string
  rate: string
  rate_type: FxRateType
  effective_date: string
  source: string
  created_by: string | null
  created_at: string
}

export interface FxRateCreatePayload {
  from_currency: string
  to_currency: string
  rate: string
  rate_type: FxRateType
  effective_date: string
  source?: string
  is_global?: boolean
}

export interface FxRateListResponse {
  rates: FxRateRecord[]
  count: number
}

export interface RevaluationRunPayload {
  org_entity_id: string
  as_of_date: string
}

export interface RevaluationRunResponse {
  run_id: string
  entity_id: string
  as_of_date: string
  functional_currency: string
  status: string
  adjustment_jv_id: string | null
  line_count: number
  total_fx_difference: string
}

export const createFxRate = async (
  payload: FxRateCreatePayload,
): Promise<FxRateRecord> => {
  const response = await apiClient.post<FxRateRecord>("/api/v1/fx/rates", payload)
  return response.data
}

export const listFxRates = async (params?: {
  from_currency?: string
  to_currency?: string
  rate_type?: FxRateType
  effective_date?: string
  limit?: number
}): Promise<FxRateListResponse> => {
  const search = new URLSearchParams()
  if (params?.from_currency) search.set("from_currency", params.from_currency)
  if (params?.to_currency) search.set("to_currency", params.to_currency)
  if (params?.rate_type) search.set("rate_type", params.rate_type)
  if (params?.effective_date) search.set("effective_date", params.effective_date)
  if (params?.limit !== undefined) search.set("limit", String(params.limit))

  const suffix = search.toString()
  const response = await apiClient.get<FxRateListResponse>(
    `/api/v1/fx/rates${suffix ? `?${suffix}` : ""}`,
  )
  return response.data
}

export const getLatestFxRate = async (params: {
  from_currency: string
  to_currency: string
  rate_type: FxRateType
  as_of_date?: string
}): Promise<FxRateRecord> => {
  const query = new URLSearchParams({
    from_currency: params.from_currency,
    to_currency: params.to_currency,
    rate_type: params.rate_type,
  })
  if (params.as_of_date) {
    query.set("as_of_date", params.as_of_date)
  }
  const response = await apiClient.get<FxRateRecord>(
    `/api/v1/fx/rates/latest?${query.toString()}`,
  )
  return response.data
}

export const runAccountingRevaluation = async (
  payload: RevaluationRunPayload,
): Promise<RevaluationRunResponse> => {
  const response = await apiClient.post<RevaluationRunResponse>(
    "/api/v1/accounting/revaluation/run",
    payload,
  )
  return response.data
}

