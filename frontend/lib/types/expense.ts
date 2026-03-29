export interface ExpenseClaim {
  id: string
  tenant_id: string
  submitted_by: string
  period: string
  claim_date: string
  vendor_name: string
  description: string
  category: string
  amount: string
  currency: string
  amount_inr: string
  receipt_url: string | null
  status: string
  policy_violation_type: string | null
  policy_violation_requires_justification: boolean
  justification: string | null
  manager_id: string | null
  manager_approved_at: string | null
  finance_approved_at: string | null
  created_at: string
}

export interface ExpenseApproval {
  id: string
  approver_id: string
  approver_role: string
  action: string
  comments: string | null
  created_at: string
}

export interface ExpensePolicy {
  id: string
  tenant_id: string
  meal_limit_per_day: string
  travel_limit_per_night: string
  receipt_required_above: string
  auto_approve_below: string
  weekend_flag_enabled: boolean
  round_number_flag_enabled: boolean
  personal_merchant_keywords: string[]
}

export interface ExpenseAnalytics {
  total_spend: string
  spend_by_category: Record<string, string>
  policy_violation_rate: string
  top_spenders: Array<{ user_id: string; user_name: string; total: string }>
  itc_recovered: string
}

export interface PaginatedResult<T> {
  data: T[]
  total: number
  limit: number
  offset: number
}
