// Fixed Assets — register, asset records, and history.

export const fixedAssetsKeys = {
  // Full key used in useQuery (all active filters)
  list: (
    entityId: string | null,
    statusFilter: string,
    locationFilter: string,
    costCentreFilter: string,
    skip: number,
    limit: number,
  ) =>
    [
      "fa-assets",
      entityId,
      statusFilter,
      locationFilter,
      costCentreFilter,
      skip,
      limit,
    ] as const,

  // Prefix used in invalidateQueries (clears all filter/page variants)
  listRoot: (entityId: string | null) => ["fa-assets", entityId] as const,

  // Full key used in useQuery
  register: (entityId: string | null, asOfDate: string, gaap: string) =>
    ["fa-register", entityId, asOfDate, gaap] as const,

  // Prefix used in invalidateQueries
  registerRoot: (entityId: string | null) =>
    ["fa-register", entityId] as const,

  locations: (entityId: string | null) =>
    ["fa-locations", entityId] as const,

  costCentres: (entityId: string | null) =>
    ["fa-cost-centres", entityId] as const,

  classes: (entityId: string | null) =>
    ["fa-classes", entityId] as const,

  asset: (id: string) => ["fa-asset", id] as const,

  depHistory: (id: string) => ["fa-dep-history", id] as const,

  revaluationHistory: (id: string) =>
    ["fa-revaluation-history", id] as const,

  impairmentHistory: (id: string) =>
    ["fa-impairment-history", id] as const,
} as const
