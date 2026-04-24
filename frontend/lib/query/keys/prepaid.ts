// Prepaid Expenses — schedules, amortisation, and entries.

export const prepaidKeys = {
  // Full key used in useQuery (all active filters)
  schedules: (
    entityId: string | null,
    statusFilter: string,
    typeFilter: string,
    locationFilter: string,
    costCentreFilter: string,
    skip: number,
    limit: number,
  ) =>
    [
      "prepaid-schedules",
      entityId,
      statusFilter,
      typeFilter,
      locationFilter,
      costCentreFilter,
      skip,
      limit,
    ] as const,

  // Prefix used in invalidateQueries (clears all filter/page variants)
  schedulesRoot: (entityId: string | null) =>
    ["prepaid-schedules", entityId] as const,

  locations: (entityId: string | null) =>
    ["prepaid-locations", entityId] as const,

  costCentres: (entityId: string | null) =>
    ["prepaid-cost-centres", entityId] as const,

  schedule: (id: string) => ["prepaid-schedule", id] as const,

  amortisation: (id: string) => ["prepaid-amortisation", id] as const,

  entries: (id: string) => ["prepaid-entries", id] as const,
} as const
