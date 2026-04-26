// Chart of Accounts — templates, hierarchy, tenant accounts.

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

  /**
   * Tenant's live chart of accounts — used by settings/chart-of-accounts and
   * journals/new. These two screens share the same key so a COA save in
   * chart-of-accounts immediately invalidates the journal account picker.
   *
   * FU-002 (Outcome B): kept separate from the ERP-mapping variants because
   * the chart-of-accounts and new-journal screens want instant consistency
   * with each other but do not need to share a cache entry with mapping
   * sessions, which may read a stale snapshot intentionally during a long
   * mapping workflow.
   */
  tenantAccounts: () => ["tenant-coa-accounts"] as const,

  /**
   * Tenant COA accounts for the erp/mappings screen.
   *
   * FU-002 (Outcome B): distinct from tenantAccounts() so that a COA save on
   * the main chart-of-accounts screen does not immediately re-fetch and
   * disrupt an in-progress ERP mapping session on this screen. Cache is
   * isolated by design.
   */
  tenantAccountsForErpMapping: () =>
    ["tenant-coa-accounts-for-erp-mapping"] as const,

  /**
   * Tenant COA accounts for the settings/erp-mapping screen.
   *
   * FU-002 (Outcome B): distinct from tenantAccountsForErpMapping() because
   * settings/erp-mapping and erp/mappings serve different mapping workflows
   * (settings-level vs. entity-level). Keeping keys separate allows each
   * screen's cache to be invalidated independently when its own mapping
   * mutations complete.
   */
  tenantAccountsForMapping: () =>
    ["tenant-coa-accounts-for-mapping"] as const,
} as const
