import apiClient from "@/lib/api/client"

export type PaginatedResult<T> = {
  items: T[]
  total: number
  skip: number
  limit: number
  has_more: boolean
}

export type LocationRecord = {
  id: string
  tenant_id: string
  entity_id: string
  location_name: string
  location_code: string
  gstin: string | null
  state_code: string | null
  address_line1: string | null
  address_line2: string | null
  city: string | null
  state: string | null
  pincode: string | null
  country_code: string
  is_primary: boolean
  is_active: boolean
  created_at: string
  updated_at: string | null
}

export type CostCentreRecord = {
  id: string
  tenant_id: string
  entity_id: string
  parent_id: string | null
  cost_centre_code: string
  cost_centre_name: string
  description: string | null
  is_active: boolean
  created_at: string
  updated_at: string | null
}

export type CostCentreTreeNode = CostCentreRecord & {
  children: CostCentreTreeNode[]
}

export type LocationStateCode = {
  code: string
  name: string
}

export type GstinValidationResult = {
  valid: boolean
  state_code: string | null
  state_name: string | null
}

export type CreateLocationPayload = {
  entity_id: string
  location_name: string
  location_code: string
  gstin?: string | null
  state_code?: string | null
  address_line1?: string | null
  address_line2?: string | null
  city?: string | null
  state?: string | null
  pincode?: string | null
  country_code?: string
  is_primary?: boolean
  is_active?: boolean
}

export type UpdateLocationPayload = Partial<
  Omit<CreateLocationPayload, "entity_id">
>

export type CreateCostCentrePayload = {
  entity_id: string
  parent_id?: string | null
  cost_centre_code: string
  cost_centre_name: string
  description?: string | null
  is_active?: boolean
}

export type UpdateCostCentrePayload = Partial<
  Omit<CreateCostCentrePayload, "entity_id">
>

export const listLocations = async (params: {
  entity_id: string
  is_active?: boolean
  skip?: number
  limit?: number
}): Promise<PaginatedResult<LocationRecord>> => {
  const search = new URLSearchParams()
  search.set("entity_id", params.entity_id)
  search.set("skip", String(params.skip ?? 0))
  search.set("limit", String(params.limit ?? 100))
  if (params.is_active !== undefined) {
    search.set("is_active", String(params.is_active))
  }
  const response = await apiClient.get<PaginatedResult<LocationRecord>>(
    `/api/v1/locations?${search.toString()}`,
  )
  return response.data
}

export const getLocation = async (locationId: string): Promise<LocationRecord> => {
  const response = await apiClient.get<LocationRecord>(
    `/api/v1/locations/${locationId}`,
  )
  return response.data
}

export const createLocation = async (
  payload: CreateLocationPayload,
): Promise<LocationRecord> => {
  const response = await apiClient.post<LocationRecord>(
    "/api/v1/locations",
    payload,
  )
  return response.data
}

export const updateLocation = async (
  locationId: string,
  payload: UpdateLocationPayload,
): Promise<LocationRecord> => {
  const response = await apiClient.patch<LocationRecord>(
    `/api/v1/locations/${locationId}`,
    payload,
  )
  return response.data
}

export const setPrimaryLocation = async (
  locationId: string,
): Promise<LocationRecord> => {
  const response = await apiClient.post<LocationRecord>(
    `/api/v1/locations/${locationId}/set-primary`,
  )
  return response.data
}

export const listCostCentres = async (params: {
  entity_id: string
  skip?: number
  limit?: number
}): Promise<PaginatedResult<CostCentreRecord>> => {
  const search = new URLSearchParams()
  search.set("entity_id", params.entity_id)
  search.set("skip", String(params.skip ?? 0))
  search.set("limit", String(params.limit ?? 100))
  const response = await apiClient.get<PaginatedResult<CostCentreRecord>>(
    `/api/v1/locations/cost-centres?${search.toString()}`,
  )
  return response.data
}

export const createCostCentre = async (
  payload: CreateCostCentrePayload,
): Promise<CostCentreRecord> => {
  const response = await apiClient.post<CostCentreRecord>(
    "/api/v1/locations/cost-centres",
    payload,
  )
  return response.data
}

export const updateCostCentre = async (
  costCentreId: string,
  payload: UpdateCostCentrePayload,
): Promise<CostCentreRecord> => {
  const response = await apiClient.patch<CostCentreRecord>(
    `/api/v1/locations/cost-centres/${costCentreId}`,
    payload,
  )
  return response.data
}

export const getCostCentreTree = async (
  entityId: string,
): Promise<CostCentreTreeNode[]> => {
  const response = await apiClient.get<CostCentreTreeNode[]>(
    `/api/v1/locations/cost-centres/tree?entity_id=${encodeURIComponent(entityId)}`,
  )
  return response.data
}

export const validateGstin = async (
  gstin: string,
): Promise<GstinValidationResult> => {
  const response = await apiClient.get<GstinValidationResult>(
    `/api/v1/locations/validate-gstin?gstin=${encodeURIComponent(gstin)}`,
  )
  return response.data
}

export const listStateCodes = async (): Promise<LocationStateCode[]> => {
  const response = await apiClient.get<LocationStateCode[]>(
    "/api/v1/locations/state-codes",
  )
  return response.data
}
