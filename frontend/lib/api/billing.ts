import { z } from "zod"
import apiClient, { parseWithSchema } from "@/lib/api/client"
import { CreditBalanceSchema } from "@/lib/schemas/credit"
import type {
  BillingCycle,
  BillingInvoice,
  BillingPlan,
  CreditBalance,
  CreditTransaction,
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

export const getCurrentSubscription = async (): Promise<TenantSubscription> => {
  const response = await apiClient.get<TenantSubscription>(
    "/api/v1/billing/subscriptions/current",
  )
  return response.data
}

export const getPlans = async (): Promise<BillingPlan[]> => {
  const response = await apiClient.get<BillingPlan[]>("/api/v1/billing/plans")
  return response.data
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
  return response.data
}

export const getInvoicePDFUrl = async (id: string): Promise<string | null> => {
  const response = await apiClient.get<BillingInvoice>(`/api/v1/billing/invoices/${id}`)
  return response.data.invoice_pdf_url
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
  const response = await apiClient.post<{ success: boolean }>(
    "/api/v1/billing/subscriptions/cancel",
    {},
  )
  return response.data
}

export const upgradeSubscription = async (
  planId: string,
  cycle: BillingCycle,
): Promise<{ success: boolean }> => {
  const response = await apiClient.post<{ success: boolean }>(
    "/api/v1/billing/subscriptions/upgrade",
    {
      plan_id: planId,
      cycle,
    },
  )
  return response.data
}
