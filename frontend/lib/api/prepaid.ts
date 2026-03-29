import apiClient from "@/lib/api/client"

export type PaginatedResult<T> = {
  items: T[]
  total: number
  skip: number
  limit: number
  has_more: boolean
}

export type PrepaidStatus = "ACTIVE" | "FULLY_AMORTISED" | "CANCELLED"

export type PrepaidSchedule = {
  id: string
  tenant_id: string
  entity_id: string
  reference_number: string
  description: string
  prepaid_type: "INSURANCE" | "SUBSCRIPTION" | "MAINTENANCE" | "RENT_ADVANCE" | "OTHER"
  vendor_name: string | null
  invoice_number: string | null
  total_amount: string
  amortised_amount: string
  remaining_amount: string
  coverage_start: string
  coverage_end: string
  amortisation_method: string
  coa_prepaid_account_id: string | null
  coa_expense_account_id: string | null
  location_id: string | null
  cost_centre_id: string | null
  status: PrepaidStatus
  created_at: string
  updated_at: string | null
}

export type PrepaidAmortisationEntry = {
  id: string
  tenant_id: string
  entity_id: string
  schedule_id: string
  period_start: string
  period_end: string
  amortisation_amount: string
  is_last_period: boolean
  run_reference: string
  created_at: string
}

export type PrepaidScheduleLine = {
  period_start: string
  period_end: string
  amount: string
  is_last_period: boolean
  is_actual: boolean
  status: string
}

export type CreatePrepaidSchedulePayload = {
  entity_id: string
  reference_number: string
  description: string
  prepaid_type: "INSURANCE" | "SUBSCRIPTION" | "MAINTENANCE" | "RENT_ADVANCE" | "OTHER"
  vendor_name?: string | null
  invoice_number?: string | null
  total_amount: string
  coverage_start: string
  coverage_end: string
  amortisation_method?: string
  coa_prepaid_account_id?: string | null
  coa_expense_account_id?: string | null
  location_id?: string | null
  cost_centre_id?: string | null
}

export const listPrepaidSchedules = async (params: {
  entity_id: string
  status?: string
  prepaid_type?: string
  location_id?: string
  cost_centre_id?: string
  skip?: number
  limit?: number
}): Promise<PaginatedResult<PrepaidSchedule>> => {
  const search = new URLSearchParams()
  search.set("entity_id", params.entity_id)
  search.set("skip", String(params.skip ?? 0))
  search.set("limit", String(params.limit ?? 20))
  if (params.status) {
    search.set("status", params.status)
  }
  if (params.prepaid_type) {
    search.set("prepaid_type", params.prepaid_type)
  }
  if (params.location_id) {
    search.set("location_id", params.location_id)
  }
  if (params.cost_centre_id) {
    search.set("cost_centre_id", params.cost_centre_id)
  }
  const response = await apiClient.get<PaginatedResult<PrepaidSchedule>>(`/api/v1/prepaid?${search.toString()}`)
  return response.data
}

export const createPrepaidSchedule = async (
  payload: CreatePrepaidSchedulePayload,
): Promise<PrepaidSchedule> => {
  const response = await apiClient.post<PrepaidSchedule>("/api/v1/prepaid", payload)
  return response.data
}

export const getPrepaidSchedule = async (id: string): Promise<PrepaidSchedule> => {
  const response = await apiClient.get<PrepaidSchedule>(`/api/v1/prepaid/${id}`)
  return response.data
}

export const updatePrepaidSchedule = async (
  id: string,
  payload: Partial<
    Pick<
      PrepaidSchedule,
      | "description"
      | "prepaid_type"
      | "vendor_name"
      | "invoice_number"
      | "status"
      | "coa_prepaid_account_id"
      | "coa_expense_account_id"
      | "location_id"
      | "cost_centre_id"
    >
  >,
): Promise<PrepaidSchedule> => {
  const response = await apiClient.patch<PrepaidSchedule>(`/api/v1/prepaid/${id}`, payload)
  return response.data
}

export const getPrepaidAmortisationSchedule = async (
  id: string,
): Promise<PrepaidScheduleLine[]> => {
  const response = await apiClient.get<PrepaidScheduleLine[]>(`/api/v1/prepaid/${id}/schedule`)
  return response.data
}

export const listPrepaidEntries = async (
  id: string,
  skip = 0,
  limit = 20,
): Promise<PaginatedResult<PrepaidAmortisationEntry>> => {
  const response = await apiClient.get<PaginatedResult<PrepaidAmortisationEntry>>(
    `/api/v1/prepaid/${id}/entries?skip=${skip}&limit=${limit}`,
  )
  return response.data
}

export const runPrepaidPeriod = async (payload: {
  entity_id: string
  period_start: string
  period_end: string
}): Promise<PrepaidAmortisationEntry[]> => {
  const response = await apiClient.post<PrepaidAmortisationEntry[]>("/api/v1/prepaid/run-period", payload)
  return response.data
}
