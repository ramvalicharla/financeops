// MIS (Management Information System) — dashboard and period list.

export const misKeys = {
  dashboard: (entityId: string | null, period: string) =>
    ["mis-dashboard", entityId, period] as const,

  periods: (entityId: string | null) =>
    ["mis-periods", entityId] as const,
} as const
