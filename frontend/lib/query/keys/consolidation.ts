// Consolidation — group-level consolidation runs and statements.

export const consolidationKeys = {
  // params is passed directly into the cache key (same shape as the API request)
  summary: (params: object | null) => ["consolidation-summary", params] as const,

  run: (runId: string | null) => ["consolidation-run", runId] as const,

  runStatements: (runId: string | null) =>
    ["consolidation-run-statements", runId] as const,
} as const
