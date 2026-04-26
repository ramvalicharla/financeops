// Org Setup — onboarding flow: summary state, template preview, COA, and ERP mapping.

export const orgSetupKeys = {
  // Main setup progress summary (shared across all setup steps and OnboardingWizard)
  summary: () => ["org-setup-summary"] as const,

  // COA template preview during Step 5
  templatePreview: (templateId: string | null) =>
    ["org-setup-template-preview", templateId] as const,

  /**
   * Tenant COA accounts fetched during the onboarding ERP mapping step (Step 6).
   *
   * FU-002 (Outcome B): kept separate from queryKeys.coa.tenantAccounts* and
   * its ERP-mapping variants. During onboarding the user has not yet completed
   * setup, so the COA data lives in a different lifecycle context. Sharing a
   * cache entry with post-setup screens would risk cross-contaminating
   * onboarding state with live dashboard state.
   */
  tenantCoaAccounts: () => ["org-setup-tenant-coa-accounts"] as const,

  // ERP field mappings configured during setup (Step 6)
  erpMappings: (entityId: string | null, connectorType: string) =>
    ["org-setup-erp-mappings", entityId, connectorType] as const,

  // ERP mapping completion summary (Step 6)
  erpSummary: (entityId: string | null, connectorType: string) =>
    ["org-setup-erp-summary", entityId, connectorType] as const,

  // Summary variant used by the consolidation hook (different staleTime)
  summaryForConsolidation: () =>
    ["org-setup-summary-for-consolidation"] as const,

  // Summary variant used by the consolidation translation page
  summaryConsolidationTranslation: () =>
    ["org-setup-summary-consolidation-translation"] as const,
} as const
