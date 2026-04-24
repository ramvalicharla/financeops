// Billing — subscription, plans, credits, invoices, entitlements, and usage.

export const billingKeys = {
  subscription: () => ["billing-subscription"] as const,

  plans: () => ["billing-plans"] as const,

  creditBalance: () => ["billing-credit-balance"] as const,

  creditLedger: () => ["billing-credit-ledger"] as const,

  invoices: () => ["billing-invoices"] as const,

  entitlements: () => ["billing-entitlements"] as const,

  // Full key used in useQuery
  usage: (periodStart: string | undefined, periodEnd: string | undefined) =>
    ["billing-usage", periodStart, periodEnd] as const,

  // Root prefix used in invalidateQueries (clears all period variants)
  usageAll: () => ["billing-usage"] as const,
} as const
