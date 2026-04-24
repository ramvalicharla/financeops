// AI — anomaly detection, narrative generation, recommendations, and audit samples.

export const aiKeys = {
  anomalies: (entityId: string | null, fromDate: string, toDate: string) =>
    ["ai-anomalies", entityId, fromDate, toDate] as const,

  dashboardAnomalies: (
    entityId: string | null,
    fromDate: string,
    toDate: string,
  ) => ["ai-dashboard-anomalies", entityId, fromDate, toDate] as const,

  dashboardRecommendations: (
    entityId: string | null,
    fromDate: string,
    toDate: string,
  ) =>
    ["ai-dashboard-recommendations", entityId, fromDate, toDate] as const,

  narrative: (entityId: string | null, fromDate: string, toDate: string) =>
    ["ai-narrative", entityId, fromDate, toDate] as const,

  varianceExplanation: (
    entityId: string | null,
    fromDate: string,
    toDate: string,
  ) =>
    ["ai-variance-explanation", entityId, fromDate, toDate] as const,

  suggestions: (entityId: string | null, fromDate: string, toDate: string) =>
    ["ai-suggestions", entityId, fromDate, toDate] as const,

  auditSamples: (
    entityId: string | null,
    fromDate: string,
    toDate: string,
  ) => ["ai-audit-samples", entityId, fromDate, toDate] as const,

  recommendations: (
    entityId: string | null,
    fromDate: string,
    toDate: string,
  ) => ["ai-recommendations", entityId, fromDate, toDate] as const,
} as const
