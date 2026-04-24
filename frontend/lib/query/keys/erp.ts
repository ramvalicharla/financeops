// ERP — connectors, sync jobs, and field mappings.

export const erpKeys = {
  connectors: () => ["erp-connectors"] as const,

  syncJobs: (connectorId: string) =>
    ["erp-sync-jobs", connectorId] as const,

  mappings: (entityId: string | null, connectorType: string) =>
    ["erp-mappings", entityId, connectorType] as const,

  mappingsSummary: (entityId: string | null, connectorType: string) =>
    ["erp-mappings-summary", entityId, connectorType] as const,
} as const
