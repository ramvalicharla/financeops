import apiClient from "@/lib/api/client"

export type PaginatedResult<T> = {
  items: T[]
  total: number
  skip: number
  limit: number
  has_more: boolean
}

export type FaAssetStatus =
  | "ACTIVE"
  | "DISPOSED"
  | "FULLY_DEPRECIATED"
  | "IMPAIRED"
  | "UNDER_INSTALLATION"

export type FaAssetClass = {
  id: string
  tenant_id: string
  entity_id: string
  name: string
  asset_type: "TANGIBLE" | "INTANGIBLE" | "ROU"
  default_method: "SLM" | "WDV" | "DOUBLE_DECLINING" | "UOP"
  default_useful_life_years: number | null
  default_residual_pct: string | null
  it_act_block_number: number | null
  it_act_depreciation_rate: string | null
  coa_asset_account_id: string | null
  coa_accum_dep_account_id: string | null
  coa_dep_expense_account_id: string | null
  is_active: boolean
  created_at: string
  updated_at: string | null
}

export type FaAsset = {
  id: string
  tenant_id: string
  entity_id: string
  asset_class_id: string
  asset_code: string
  asset_name: string
  description: string | null
  location: string | null
  serial_number: string | null
  purchase_date: string
  capitalisation_date: string
  original_cost: string
  residual_value: string
  useful_life_years: string
  depreciation_method: string
  it_act_block_number: number | null
  status: FaAssetStatus
  disposal_date: string | null
  disposal_proceeds: string | null
  gaap_overrides: Record<string, unknown> | null
  location_id: string | null
  cost_centre_id: string | null
  is_active: boolean
  created_at: string
  updated_at: string | null
}

export type FaDepreciationRun = {
  id: string
  tenant_id: string
  entity_id: string
  asset_id: string
  run_date: string
  period_start: string
  period_end: string
  gaap: string
  depreciation_method: string
  opening_nbv: string
  depreciation_amount: string
  closing_nbv: string
  accumulated_dep: string
  run_reference: string
  is_reversal: boolean
  created_at: string
}

export type FaRevaluation = {
  id: string
  tenant_id: string
  entity_id: string
  asset_id: string
  revaluation_date: string
  pre_revaluation_cost: string
  pre_revaluation_accum_dep: string
  pre_revaluation_nbv: string
  fair_value: string
  revaluation_surplus: string
  method: string
  created_at: string
}

export type FaImpairment = {
  id: string
  tenant_id: string
  entity_id: string
  asset_id: string
  impairment_date: string
  pre_impairment_nbv: string
  recoverable_amount: string
  value_in_use: string | null
  fvlcts: string | null
  impairment_loss: string
  discount_rate: string | null
  created_at: string
}

export type FaRegisterLine = {
  asset_code: string
  asset_name: string
  class_name: string
  purchase_date: string
  capitalisation_date: string
  original_cost: string
  accumulated_dep: string
  nbv: string
  ytd_depreciation: string
  status: string
}

export type CreateAssetClassPayload = {
  entity_id: string
  name: string
  asset_type: "TANGIBLE" | "INTANGIBLE" | "ROU"
  default_method: "SLM" | "WDV" | "DOUBLE_DECLINING" | "UOP"
  default_useful_life_years?: number
  default_residual_pct?: string
  it_act_block_number?: number
  it_act_depreciation_rate?: string
  coa_asset_account_id?: string | null
  coa_accum_dep_account_id?: string | null
  coa_dep_expense_account_id?: string | null
  is_active?: boolean
}

export type CreateAssetPayload = {
  entity_id: string
  asset_class_id: string
  asset_code: string
  asset_name: string
  description?: string | null
  location?: string | null
  serial_number?: string | null
  purchase_date: string
  capitalisation_date: string
  original_cost: string
  residual_value?: string
  useful_life_years: string
  depreciation_method: "SLM" | "WDV" | "DOUBLE_DECLINING" | "UOP"
  it_act_block_number?: number | null
  status?: FaAssetStatus
  gaap_overrides?: Record<string, unknown> | null
  location_id?: string | null
  cost_centre_id?: string | null
  is_active?: boolean
}

export const listAssetClasses = async (
  entityId: string,
  skip = 0,
  limit = 100,
): Promise<PaginatedResult<FaAssetClass>> => {
  const response = await apiClient.get<PaginatedResult<FaAssetClass>>(
    `/api/v1/fixed-assets/asset-classes?entity_id=${encodeURIComponent(entityId)}&skip=${skip}&limit=${limit}`,
  )
  return response.data
}

export const createAssetClass = async (payload: CreateAssetClassPayload): Promise<FaAssetClass> => {
  const response = await apiClient.post<FaAssetClass>("/api/v1/fixed-assets/asset-classes", payload)
  return response.data
}

export const updateAssetClass = async (
  id: string,
  payload: Partial<Omit<CreateAssetClassPayload, "entity_id">>,
): Promise<FaAssetClass> => {
  const response = await apiClient.patch<FaAssetClass>(`/api/v1/fixed-assets/asset-classes/${id}`, payload)
  return response.data
}

export const listAssets = async (params: {
  entity_id: string
  status?: string
  location_id?: string
  cost_centre_id?: string
  skip?: number
  limit?: number
}): Promise<PaginatedResult<FaAsset>> => {
  const search = new URLSearchParams()
  search.set("entity_id", params.entity_id)
  search.set("skip", String(params.skip ?? 0))
  search.set("limit", String(params.limit ?? 20))
  if (params.status) {
    search.set("status", params.status)
  }
  if (params.location_id) {
    search.set("location_id", params.location_id)
  }
  if (params.cost_centre_id) {
    search.set("cost_centre_id", params.cost_centre_id)
  }
  const response = await apiClient.get<PaginatedResult<FaAsset>>(`/api/v1/fixed-assets?${search.toString()}`)
  return response.data
}

export const createAsset = async (payload: CreateAssetPayload): Promise<FaAsset> => {
  const response = await apiClient.post<FaAsset>("/api/v1/fixed-assets", payload)
  return response.data
}

export const getAsset = async (id: string): Promise<FaAsset> => {
  const response = await apiClient.get<FaAsset>(`/api/v1/fixed-assets/${id}`)
  return response.data
}

export const updateAsset = async (
  id: string,
  payload: Partial<Pick<FaAsset, "asset_name" | "description" | "location" | "serial_number" | "status" | "is_active" | "location_id" | "cost_centre_id">> & {
    gaap_overrides?: Record<string, unknown> | null
  },
): Promise<FaAsset> => {
  const response = await apiClient.patch<FaAsset>(`/api/v1/fixed-assets/${id}`, payload)
  return response.data
}

export const runAssetDepreciation = async (
  id: string,
  payload: { period_start: string; period_end: string; gaap?: string },
): Promise<FaDepreciationRun> => {
  const response = await apiClient.post<FaDepreciationRun>(`/api/v1/fixed-assets/${id}/depreciation-run`, payload)
  return response.data
}

export const listDepreciationHistory = async (
  id: string,
  skip = 0,
  limit = 20,
): Promise<PaginatedResult<FaDepreciationRun>> => {
  const response = await apiClient.get<PaginatedResult<FaDepreciationRun>>(
    `/api/v1/fixed-assets/${id}/depreciation-history?skip=${skip}&limit=${limit}`,
  )
  return response.data
}

export const postRevaluation = async (
  id: string,
  payload: { fair_value: string; method: "PROPORTIONAL" | "ELIMINATION"; revaluation_date: string },
): Promise<FaRevaluation> => {
  const response = await apiClient.post<FaRevaluation>(`/api/v1/fixed-assets/${id}/revaluation`, payload)
  return response.data
}

export const listRevaluationHistory = async (id: string): Promise<FaRevaluation[]> => {
  const response = await apiClient.get<FaRevaluation[]>(`/api/v1/fixed-assets/${id}/revaluation-history`)
  return response.data
}

export const postImpairment = async (
  id: string,
  payload: { value_in_use?: string; fvlcts?: string; discount_rate?: string; impairment_date: string },
): Promise<FaImpairment> => {
  const response = await apiClient.post<FaImpairment>(`/api/v1/fixed-assets/${id}/impairment`, payload)
  return response.data
}

export const listImpairmentHistory = async (id: string): Promise<FaImpairment[]> => {
  const response = await apiClient.get<FaImpairment[]>(`/api/v1/fixed-assets/${id}/impairment-history`)
  return response.data
}

export const disposeAsset = async (
  id: string,
  payload: { disposal_date: string; proceeds: string },
): Promise<FaAsset> => {
  const response = await apiClient.post<FaAsset>(`/api/v1/fixed-assets/${id}/dispose`, payload)
  return response.data
}

export const getFixedAssetRegister = async (params: {
  entity_id: string
  as_of_date: string
  gaap?: string
}): Promise<FaRegisterLine[]> => {
  const search = new URLSearchParams()
  search.set("entity_id", params.entity_id)
  search.set("as_of_date", params.as_of_date)
  if (params.gaap) {
    search.set("gaap", params.gaap)
  }
  const response = await apiClient.get<FaRegisterLine[]>(`/api/v1/fixed-assets/register?${search.toString()}`)
  return response.data
}

export const runPeriodDepreciation = async (payload: {
  entity_id: string
  period_start: string
  period_end: string
  gaap?: string
}): Promise<FaDepreciationRun[]> => {
  const response = await apiClient.post<FaDepreciationRun[]>("/api/v1/fixed-assets/run-period-depreciation", payload)
  return response.data
}
