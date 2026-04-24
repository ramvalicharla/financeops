import { z } from "zod"
import apiClient, { parseWithSchema } from "@/lib/api/client"
import { CreditBalanceSchema } from "@/lib/schemas/credit"
import type {
  BillingCycle,
  BillingEntitlement,
  BillingInvoice,
  BillingPlan,
  CreditBalance,
  CreditTransaction,
  BillingUsageAggregate,
  TenantSubscription,
} from "@/types/billing"

const legacyCreditBalanceSchema = z.object({
  current_balance: z.number(),
  included_in_plan: z.number(),
  used_this_period: z.number(),
  expires_at: z.string().nullable(),
})

const modernCreditBalanceSchema = CreditBalanceSchema.transform((payload) => ({
  current_balance: Number(payload.balance),
  included_in_plan: Number(payload.balance) + Number(payload.reserved),
  used_this_period: Number(payload.reserved),
  expires_at: null,
}))

const creditBalanceApiSchema = z.union([
  legacyCreditBalanceSchema,
  modernCreditBalanceSchema,
])

export const getCurrentSubscription = async (): Promise<TenantSubscription | null> => {
  const response = await apiClient.get<TenantSubscription>(
    "/api/v1/billing/subscriptions/current",
  )
  const payload = response.data as unknown
  if (payload && typeof payload === "object" && "item" in payload) {
    return (payload as { item: TenantSubscription | null }).item ?? null
  }
  return (payload as TenantSubscription) ?? null
}

export const getPlans = async (): Promise<BillingPlan[]> => {
  const response = await apiClient.get<BillingPlan[]>("/api/v1/billing/plans")
  const payload = response.data as unknown
  if (Array.isArray(payload)) {
    return payload as BillingPlan[]
  }
  if (payload && typeof payload === "object" && "items" in payload) {
    return ((payload as { items: BillingPlan[] }).items ?? []) as BillingPlan[]
  }
  return []
}

export const getCreditBalance = async (): Promise<CreditBalance> => {
  const endpoint = "/api/v1/billing/credits/balance"
  const response = await apiClient.get<unknown>(endpoint)
  return parseWithSchema(endpoint, response.data, creditBalanceApiSchema) as CreditBalance
}

export const getCreditLedger = async (): Promise<CreditTransaction[]> => {
  const response = await apiClient.get<CreditTransaction[]>(
    "/api/v1/billing/credits/ledger",
  )
  return response.data
}

export const getInvoices = async (): Promise<BillingInvoice[]> => {
  const response = await apiClient.get<BillingInvoice[]>("/api/v1/billing/invoices")
  const payload = response.data as unknown
  if (Array.isArray(payload)) {
    return payload as BillingInvoice[]
  }
  if (payload && typeof payload === "object" && "items" in payload) {
    return ((payload as { items: BillingInvoice[] }).items ?? []) as BillingInvoice[]
  }
  return []
}

export const getInvoicePDFUrl = async (id: string): Promise<string | null> => {
  const response = await apiClient.get<unknown>(`/api/v1/billing/invoices/${id}`)
  const payload = response.data as unknown
  const invoice: BillingInvoice | null =
    payload && typeof payload === "object" && "data" in payload
      ? ((payload as { data: BillingInvoice }).data ?? null)
      : (payload as BillingInvoice) ?? null
  return invoice?.invoice_pdf_url ?? null
}

export const createTopUp = async (
  credits: number,
): Promise<{ success: boolean }> => {
  const response = await apiClient.post<{ success: boolean }>(
    "/api/v1/billing/credits/top-up",
    { credits },
  )
  return response.data
}

export const cancelSubscription = async (): Promise<{ success: boolean }> => {
  const current = await getCurrentSubscription()
  if (!current?.id) {
    throw new Error("No active subscription found")
  }
  const response = await apiClient.post<{ success: boolean }>(
    "/api/v1/billing/subscriptions/cancel",
    { subscription_id: current.id },
  )
  return response.data
}

export const upgradeSubscription = async (
  planId: string,
  cycle: BillingCycle,
): Promise<{ success: boolean }> => {
  const current = await getCurrentSubscription()
  if (!current?.id) {
    throw new Error("No active subscription found")
  }
  const response = await apiClient.post<{ success: boolean }>(
    "/api/v1/billing/subscriptions/upgrade",
    {
      subscription_id: current.id,
      to_plan_id: planId,
      billing_cycle: cycle,
    },
  )
  return response.data
}

export const getCurrentEntitlements = async (): Promise<BillingEntitlement[]> => {
  const response = await apiClient.get<{ items: BillingEntitlement[] }>(
    "/api/v1/billing/entitlements/current",
  )
  return response.data.items ?? []
}

export const refreshEntitlements = async (): Promise<{ inserted: number; features: string[] }> => {
  const response = await apiClient.post<{ inserted: number; features: string[] }>(
    "/api/v1/billing/entitlements/refresh",
    {},
  )
  return response.data
}

export const getUsageAggregates = async (params?: {
  period_start?: string
  period_end?: string
}): Promise<BillingUsageAggregate[]> => {
  const search = new URLSearchParams()
  if (params?.period_start) {
    search.set("period_start", params.period_start)
  }
  if (params?.period_end) {
    search.set("period_end", params.period_end)
  }
  const suffix = search.toString() ? `?${search.toString()}` : ""
  const response = await apiClient.get<{ items: BillingUsageAggregate[] }>(
    `/api/v1/billing/usage${suffix}`,
  )
  return response.data.items ?? []
}

export const recordUsage = async (payload: {
  feature_name: string
  usage_quantity?: number
  reference_type?: string
  reference_id?: string
}): Promise<{ allowed: boolean }> => {
  const response = await apiClient.post<{ allowed: boolean }>(
    "/api/v1/billing/usage/record",
    payload,
  )
  return response.data
}

export const generateInvoice = async (payload?: {
  subscription_id?: string
  due_in_days?: number
}): Promise<{ invoice_id: string; status: string; amount: string }> => {
  const response = await apiClient.post<{ invoice_id: string; status: string; amount: string }>(
    "/api/v1/billing/generate-invoice",
    payload ?? {},
  )
  return response.data
}

export const createCheckoutSession = async (returnUrl: string): Promise<{ url: string; provider: string }> => {
  const response = await apiClient.post<{ url: string; provider: string }>(
    "/api/v1/billing/checkout",
    { return_url: returnUrl },
  )
  return response.data
}
