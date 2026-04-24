// Chart of Accounts — templates, hierarchy, tenant accounts.
//
// NOTE: The four tenant-coa-accounts keys are intentionally kept separate.
// They map to different API paths / data shapes and should not be unified yet.
// Follow-up: refactor(coa): unify tenant-coa-accounts query keys

export const coaKeys = {
  templates: () => ["coa-templates"] as const,

  hierarchy: (templateId: string | null, gaap: string) =>
    ["coa-hierarchy", templateId, gaap] as const,

  // Full key for fetching accounts by template
  effectiveAccounts: (templateId: string | null) =>
    ["coa-effective-accounts", templateId] as const,

  // Root prefix for broad invalidation (no templateId)
  effectiveAccountsAll: () => ["coa-effective-accounts"] as const,

  uploadBatches: () => ["coa-upload-batches"] as const,

  // settings/chart-of-accounts + journals/new (tenant's live COA)
  tenantAccounts: () => ["tenant-coa-accounts"] as const,

  // erp/mappings (same resource, dedicated key for isolated cache)
  tenantAccountsForErpMapping: () =>
    ["tenant-coa-accounts-for-erp-mapping"] as const,

  // settings/erp-mapping (same resource, dedicated key for isolated cache)
  tenantAccountsForMapping: () =>
    ["tenant-coa-accounts-for-mapping"] as const,
} as const
