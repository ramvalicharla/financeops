import apiClient from "@/lib/api/client"

export type AnalyticsMetricRow = {
  metric_name: string
  metric_value: string
  unit: string
  dimension: Record<string, unknown>
}

export type AlertEvaluationRow = {
  metric_name: string
  metric_value: string
  threshold: string
  condition: "GT" | "LT" | "ABS_GT"
  triggered: boolean
  description?: string | null
}

export type KpiResponse = {
  rows: AnalyticsMetricRow[]
  snapshot: {
    snapshot_id: string
    snapshot_type: string
    as_of_date: string
    period_from?: string | null
    period_to?: string | null
  }
  lineage: Record<string, unknown>
  alerts: AlertEvaluationRow[]
}

export type VarianceMetricRow = {
  metric_name: string
  current_value: string
  previous_value: string
  variance_value: string
  variance_percent?: string | null
}

export type AccountVarianceRow = {
  account_code: string
  account_name: string
  current_value: string
  previous_value: string
  variance_value: string
  variance_percent?: string | null
}

export type VarianceResponse = {
  comparison: string
  current_period: { from_date: string; to_date: string }
  previous_period: { from_date: string; to_date: string }
  metric_variances: VarianceMetricRow[]
  account_variances: AccountVarianceRow[]
}

export type TrendPoint = { period: string; value: string }
export type TrendSeries = { metric_name: string; points: TrendPoint[] }
export type TrendResponse = { frequency: string; series: TrendSeries[] }

export type RatioResponse = {
  rows: AnalyticsMetricRow[]
  snapshot: {
    snapshot_id: string
    snapshot_type: string
    as_of_date: string
    period_from?: string | null
    period_to?: string | null
  }
  lineage: Record<string, unknown>
}

export type DrilldownResponse = {
  metric_name: string
  accounts: Array<{ account_code: string; account_name: string; amount: string }>
  journals: Array<{
    journal_id: string
    journal_number: string
    journal_date: string
    status: string
    source_ref?: string | null
  }>
  gl_entries: Array<{
    gl_entry_id: string
    account_code: string
    account_name: string
    debit_amount: string
    credit_amount: string
    source_ref?: string | null
    created_at: string
  }>
  lineage: Record<string, unknown>
}

const buildQuery = (params: Record<string, string | undefined>) => {
  const query = new URLSearchParams()
  Object.entries(params).forEach(([key, value]) => {
    if (value) query.set(key, value)
  })
  return query.toString() ? `?${query.toString()}` : ""
}

export const getKpis = async (params: {
  org_entity_id?: string
  org_group_id?: string
  as_of_date?: string
  from_date?: string
  to_date?: string
}): Promise<KpiResponse> => {
  const suffix = buildQuery(params)
  const response = await apiClient.get<KpiResponse>(`/api/v1/analytics/kpis${suffix}`)
  return response.data
}

export const getVariance = async (params: {
  org_entity_id?: string
  org_group_id?: string
  from_date: string
  to_date: string
  comparison?: string
}): Promise<VarianceResponse> => {
  const suffix = buildQuery(params)
  const response = await apiClient.get<VarianceResponse>(`/api/v1/analytics/variance${suffix}`)
  return response.data
}

export const getTrends = async (params: {
  org_entity_id?: string
  org_group_id?: string
  from_date: string
  to_date: string
  frequency?: string
}): Promise<TrendResponse> => {
  const suffix = buildQuery(params)
  const response = await apiClient.get<TrendResponse>(`/api/v1/analytics/trends${suffix}`)
  return response.data
}

export const getRatios = async (params: {
  org_entity_id?: string
  org_group_id?: string
  as_of_date?: string
  from_date?: string
  to_date?: string
}): Promise<RatioResponse> => {
  const suffix = buildQuery(params)
  const response = await apiClient.get<RatioResponse>(`/api/v1/analytics/ratios${suffix}`)
  return response.data
}

export const getDrilldown = async (params: {
  metric_name: string
  org_entity_id?: string
  org_group_id?: string
  from_date: string
  to_date: string
  as_of_date?: string
}): Promise<DrilldownResponse> => {
  const suffix = buildQuery(params)
  const response = await apiClient.get<DrilldownResponse>(`/api/v1/analytics/drilldown${suffix}`)
  return response.data
}

