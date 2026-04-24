// Close Governance — period lock, readiness checks, and month-end checklists.

export const closeKeys = {
  // Full key used in useQuery
  periodStatus: (entityId: string | null, fiscalYear: number, periodNumber: number) =>
    ["period-status", entityId, fiscalYear, periodNumber] as const,

  // Root prefix for broad invalidation (clears all entities/periods at once)
  periodStatusAll: () => ["period-status"] as const,

  // Full key used in useQuery
  readiness: (entityId: string | null, fiscalYear: number, periodNumber: number) =>
    ["close-readiness", entityId, fiscalYear, periodNumber] as const,

  // Root prefix for broad invalidation
  readinessAll: () => ["close-readiness"] as const,

  // Keyed by entity name (the API filters by name, not UUID)
  monthendList: (entityName: string | null) =>
    ["monthend-checklists", entityName] as const,

  // Root prefix for broad invalidation
  monthendListAll: () => ["monthend-checklists"] as const,

  monthendDetail: (checklistId: string | null) =>
    ["monthend-checklist", checklistId] as const,

  // Root prefix for broad invalidation
  monthendDetailAll: () => ["monthend-checklist"] as const,
} as const
