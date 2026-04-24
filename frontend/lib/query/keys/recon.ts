// Reconciliation — GL/TB and payroll reconciliation results.

export const reconKeys = {
  gltbResult: (entityId: string | null, period: string | null, runId: string | null) =>
    ["gltb-result", entityId, period, runId] as const,

  gltbAccountEntries: (
    entityId: string | null,
    accountCode: string | null,
    period: string | null,
  ) => ["gltb-account-entries", entityId, accountCode, period] as const,

  payrollRecon: (
    entityId: string | null,
    period: string | null,
    runId: string | null,
  ) => ["payroll-recon", entityId, period, runId] as const,

  payrollCostCentreDetail: (
    entityId: string | null,
    costCentreId: string | null,
    period: string | null,
  ) =>
    ["payroll-cost-centre-detail", entityId, costCentreId, period] as const,
} as const
