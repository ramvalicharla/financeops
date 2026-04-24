export type AdminPaginatedResponse<T> = {
  items: T[]
  total: number
  limit: number
  offset: number
}

export type AdminTenantListItem = {
  id: string
  name: string
  slug: string
  status: string
  plan_tier: string | null
  trial_end_date: string | null
  credit_balance: number
  user_count: number
  created_at: string
}

export type AdminSubscription = {
  id: string
  plan_id: string
  status: string
  billing_cycle: string
  trial_end_date: string | null
  current_period_start: string
  current_period_end: string
}

export type AdminInvoice = {
  id: string
  status: string
  total: string
  currency: string
  due_date: string
  created_at: string
}

export type AdminCreditEntry = {
  id: string
  transaction_type: string
  credits_delta: number
  credits_balance_after: number
  created_at: string
}

export type AdminTenantDetail = {
  tenant: {
    id: string
    name: string
    slug: string
    status: string
    country: string
    created_at: string
  }
  subscription: AdminSubscription | null
  credit_balance: number
  recent_invoices: AdminInvoice[]
  recent_credits: AdminCreditEntry[]
}

export type AdminCreditRow = {
  tenant_id: string
  tenant_name: string
  credit_balance: number
  last_transaction_at: string | null
}

export type AdminBillingPlan = {
  id: string
  name: string
  plan_tier: string
  pricing_type: string
  price: string | null
  billing_cycle: string
  currency: string
  included_credits: number
  max_entities: number
  max_connectors: number
  max_users: number
  trial_days: number
  is_active: boolean
  modules_enabled: Record<string, boolean>
  created_at: string
}

export type AdminPlanFormValues = {
  name: string
  plan_tier: "starter" | "professional" | "enterprise"
  pricing_type: "flat" | "tiered" | "usage" | "hybrid"
  price: string
  billing_cycle: "monthly" | "annual"
  currency: string
  included_credits: number
  max_entities: number
  max_connectors: number
  max_users: number
  trial_days: number
  is_active: boolean
  modules_enabled: Record<string, boolean>
}
