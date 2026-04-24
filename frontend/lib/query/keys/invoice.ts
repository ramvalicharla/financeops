// Invoice Classifier — review queue, history, and classification rules.

export const invoiceKeys = {
  // Full key used in useQuery
  queue: (entityId: string | null, skip: number, limit: number) =>
    ["invoice-review-queue", entityId, skip, limit] as const,

  // Prefix used in invalidateQueries (clears all skip/limit variants)
  queueRoot: (entityId: string | null) =>
    ["invoice-review-queue", entityId] as const,

  // Full key used in useQuery
  history: (
    entityId: string | null,
    classification: string,
    method: string,
    skip: number,
    limit: number,
  ) =>
    [
      "invoice-history",
      entityId,
      classification,
      method,
      skip,
      limit,
    ] as const,

  // Prefix used in invalidateQueries (clears all filter/page variants)
  historyRoot: (entityId: string | null) =>
    ["invoice-history", entityId] as const,

  rules: () => ["invoice-rules"] as const,
} as const
