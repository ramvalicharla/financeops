export type SubscriptionStatus =
  | "trialing"
  | "active"
  | "past_due"
  | "grace_period"
  | "suspended"
  | "cancelled"
  | "incomplete"

export type BillingCycle = "monthly" | "annual"

export interface BillingPlan {
  id: string
  plan_tier: "starter" | "professional" | "enterprise"
  billing_cycle: BillingCycle
  base_price_inr: string
  base_price_usd: string
  included_credits: number
  max_entities: number
  max_connectors: number
  trial_days: number
  annual_discount_pct: string
}

export interface TenantSubscription {
  id: string
  plan: BillingPlan
  status: SubscriptionStatus
  billing_cycle: BillingCycle
  current_period_start: string
  current_period_end: string
  trial_end: string | null
  billing_country: string
  billing_currency: string
  provider: "stripe" | "razorpay"
}

export interface CreditBalance {
  current_balance: number
  included_in_plan: number
  used_this_period: number
  expires_at: string | null
}

export interface CreditTransaction {
  id: string
  transaction_type: string
  credits_delta: number
  credits_balance_after: number
  description: string
  created_at: string
}

export interface BillingInvoice {
  id: string
  provider_invoice_id: string
  status: "draft" | "open" | "paid" | "void" | "uncollectible"
  currency: string
  total: string
  due_date: string
  paid_at: string | null
  invoice_pdf_url: string | null
  created_at: string
}
