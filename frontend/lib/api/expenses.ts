import apiClient from "@/lib/api/client"
import type {
  ExpenseAnalytics,
  ExpenseClaim,
  ExpensePolicy,
  PaginatedResult,
} from "@/lib/types/expense"

export interface SubmitExpensePayload {
  entity_id?: string | null
  location_id?: string | null
  cost_centre_id?: string | null
  vendor_name: string
  description: string
  category: string
  amount: string
  currency: string
  claim_date: string
  has_receipt: boolean
  receipt_url?: string | null
  justification?: string | null
}

export const submitExpense = async (payload: SubmitExpensePayload): Promise<ExpenseClaim> => {
  const response = await apiClient.post<ExpenseClaim>("/api/v1/expenses", payload)
  return response.data
}

export const listExpenses = async (params?: {
  entity_id?: string
  location_id?: string
  cost_centre_id?: string
  status?: string
  period?: string
  submitted_by?: string
  limit?: number
  offset?: number
}): Promise<PaginatedResult<ExpenseClaim>> => {
  const search = new URLSearchParams()
  if (params?.entity_id) search.set("entity_id", params.entity_id)
  if (params?.location_id) search.set("location_id", params.location_id)
  if (params?.cost_centre_id) search.set("cost_centre_id", params.cost_centre_id)
  if (params?.status) search.set("status", params.status)
  if (params?.period) search.set("period", params.period)
  if (params?.submitted_by) search.set("submitted_by", params.submitted_by)
  if (params?.limit !== undefined) search.set("limit", String(params.limit))
  if (params?.offset !== undefined) search.set("offset", String(params.offset))
  const query = search.toString()
  const response = await apiClient.get<PaginatedResult<ExpenseClaim>>(
    `/api/v1/expenses${query ? `?${query}` : ""}`,
  )
  return response.data
}

export const getExpenseClaim = async (
  claimId: string,
): Promise<ExpenseClaim & { approvals: Array<{ id: string; approver_id: string; approver_role: string; action: string; comments: string | null; created_at: string }> }> => {
  const response = await apiClient.get<
    ExpenseClaim & {
      approvals: Array<{
        id: string
        approver_id: string
        approver_role: string
        action: string
        comments: string | null
        created_at: string
      }>
    }
  >(`/api/v1/expenses/${claimId}`)
  return response.data
}

export const approveExpenseClaim = async (
  claimId: string,
  action: "approved" | "rejected" | "returned",
  comments?: string,
): Promise<{ id: string; status: string; manager_approved_at: string | null; finance_approved_at: string | null }> => {
  const response = await apiClient.post(`/api/v1/expenses/${claimId}/approve`, {
    action,
    comments: comments ?? null,
  })
  return response.data
}

export const getExpenseAnalytics = async (period?: string): Promise<ExpenseAnalytics> => {
  const query = period ? `?period=${encodeURIComponent(period)}` : ""
  const response = await apiClient.get<ExpenseAnalytics>(`/api/v1/expenses/analytics${query}`)
  return response.data
}

export const getExpensePolicy = async (): Promise<ExpensePolicy> => {
  const response = await apiClient.get<ExpensePolicy>("/api/v1/expenses/policy")
  return response.data
}

export const patchExpensePolicy = async (
  payload: Partial<{
    meal_limit_per_day: string
    travel_limit_per_night: string
    receipt_required_above: string
    auto_approve_below: string
    weekend_flag_enabled: boolean
    round_number_flag_enabled: boolean
    personal_merchant_keywords: string[]
  }>,
): Promise<ExpensePolicy> => {
  const response = await apiClient.patch<ExpensePolicy>("/api/v1/expenses/policy", payload)
  return response.data
}
