// Accounting — GL statements, journals, and trial balance.

export const accountingKeys = {
  balanceSheet: (entityId: string | null, asOfDate: string) =>
    ["balance-sheet", entityId, asOfDate] as const,

  cashFlow: (entityId: string | null, fromDate: string, toDate: string) =>
    ["cash-flow", entityId, fromDate, toDate] as const,

  pnl: (entityId: string | null, fromDate: string, toDate: string) =>
    ["pnl", entityId, fromDate, toDate] as const,

  trialBalance: (
    entityId: string | null,
    asOfDate: string,
    fromDate: string,
    toDate: string,
  ) => ["accounting-trial-balance", entityId, asOfDate, fromDate, toDate] as const,

  // Journals filtered to those that touch a specific account (used in TB drilldown)
  journalsForTb: (entityId: string | null) =>
    ["accounting-journals-for-tb", entityId] as const,

  // Full list key (includes pagination)
  journals: (entityId: string | null, skip: number, limit: number) =>
    ["accounting-journals", entityId, skip, limit] as const,

  // Root prefix for broad invalidation (e.g. after push/reversal)
  journalsAll: () => ["accounting-journals"] as const,

  journal: (journalId: string) => ["accounting-journal", journalId] as const,
} as const
