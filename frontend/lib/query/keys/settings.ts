// Settings — cost centres, locations, and entity location data.

export const settingsKeys = {
  costCentresFlat: (entityId: string | null) =>
    ["settings-cost-centres-flat", entityId] as const,

  costCentresTree: (entityId: string | null) =>
    ["settings-cost-centres-tree", entityId] as const,

  // Full key used in useQuery
  locations: (entityId: string | null, skip: number, limit: number) =>
    ["settings-locations", entityId, skip, limit] as const,

  // Prefix used in invalidateQueries (clears all skip/limit variants)
  locationsAll: (entityId: string | null) =>
    ["settings-locations", entityId] as const,

  // Entity locations — used by EntityLocationSelector and settings/locations invalidation
  entityLocations: (entityId: string | null) =>
    ["entity-locations", entityId] as const,

  indiaStateCodes: () => ["india-state-codes"] as const,

  // Active location for the workspace (used by useLocation hook)
  activeLocation: (locationId: string | null) =>
    ["active-location", locationId] as const,
} as const
