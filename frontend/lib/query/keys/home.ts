// Home dashboard — summary widgets that each fetch their own slice.

export const homeKeys = {
  erpConnectors: () => ["home-erp-connectors"] as const,

  pendingApprovals: (entityId: string | null) =>
    ["home-pending-approvals", entityId] as const,

  openAnomalies: () => ["home-open-anomalies"] as const,

  recentJournals: (entityId: string | null) =>
    ["home-recent-journals", entityId] as const,
} as const
