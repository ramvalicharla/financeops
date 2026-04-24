// Analytics — KPIs, trends, ratios, and variance across dashboard views.

export const analyticsKeys = {
  kpisCfo: (entityId: string | null, fromDate: string, toDate: string) =>
    ["analytics-kpis-cfo", entityId, fromDate, toDate] as const,

  trendsCfo: (entityId: string | null, fromDate: string, toDate: string) =>
    ["analytics-trends-cfo", entityId, fromDate, toDate] as const,

  kpis: (entityId: string | null, fromDate: string, toDate: string) =>
    ["analytics-kpis-page", entityId, fromDate, toDate] as const,

  kpiDrilldown: (
    entityId: string | null,
    metric: string | null,
    fromDate: string,
    toDate: string,
  ) =>
    ["analytics-kpi-drilldown", entityId, metric, fromDate, toDate] as const,

  ratios: (entityId: string | null, fromDate: string, toDate: string) =>
    ["analytics-ratios", entityId, fromDate, toDate] as const,

  trends: (
    entityId: string | null,
    fromDate: string,
    toDate: string,
    frequency: string,
  ) =>
    ["analytics-trends-page", entityId, fromDate, toDate, frequency] as const,

  variance: (
    entityId: string | null,
    fromDate: string,
    toDate: string,
    comparison: string,
  ) =>
    ["analytics-variance", entityId, fromDate, toDate, comparison] as const,
} as const
