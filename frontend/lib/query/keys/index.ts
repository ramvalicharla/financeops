// Canonical query key factory for the Finqor frontend.
//
// All query keys must be produced from this file. Do not write inline
// query key arrays anywhere else in the codebase.
//
// Import pattern:
//   import { queryKeys } from "@/lib/query/keys"
//
// Usage:
//   queryKey: queryKeys.accounting.journals(entityId, skip, limit)
//   queryClient.invalidateQueries({ queryKey: queryKeys.accounting.journalsAll() })
//
// controlPlaneQueryKeys are in lib/query/controlPlane.ts (pre-existing factory, not migrated here).

import { accountingKeys } from "./accounting"
import { aiKeys } from "./ai"
import { analyticsKeys } from "./analytics"
import { authKeys } from "./auth"
import { billingKeys } from "./billing"
import { closeKeys } from "./close"
import { coaKeys } from "./coa"
import { consolidationKeys } from "./consolidation"
import { erpKeys } from "./erp"
import { fixedAssetsKeys } from "./fixed-assets"
import { fxKeys } from "./fx"
import { homeKeys } from "./home"
import { invoiceKeys } from "./invoice"
import { misKeys } from "./mis"
import { orgSetupKeys } from "./orgSetup"
import { platformKeys } from "./platform"
import { prepaidKeys } from "./prepaid"
import { reconKeys } from "./recon"
import { searchKeys } from "./search"
import { settingsKeys } from "./settings"
import { syncKeys } from "./sync"
import { tenantProfileKeys } from "./tenantProfile"
import { workspaceKeys } from "./workspace"

export const queryKeys = {
  accounting: accountingKeys,
  ai: aiKeys,
  analytics: analyticsKeys,
  auth: authKeys,
  billing: billingKeys,
  close: closeKeys,
  coa: coaKeys,
  consolidation: consolidationKeys,
  erp: erpKeys,
  fixedAssets: fixedAssetsKeys,
  fx: fxKeys,
  home: homeKeys,
  invoice: invoiceKeys,
  mis: misKeys,
  orgSetup: orgSetupKeys,
  platform: platformKeys,
  prepaid: prepaidKeys,
  recon: reconKeys,
  search: searchKeys,
  settings: settingsKeys,
  sync: syncKeys,
  tenantProfile: tenantProfileKeys,
  workspace: workspaceKeys,
} as const

// Re-export individual domain objects for callers that only need one domain.
export {
  accountingKeys,
  aiKeys,
  analyticsKeys,
  authKeys,
  billingKeys,
  closeKeys,
  coaKeys,
  consolidationKeys,
  erpKeys,
  fixedAssetsKeys,
  fxKeys,
  homeKeys,
  invoiceKeys,
  misKeys,
  orgSetupKeys,
  platformKeys,
  prepaidKeys,
  reconKeys,
  searchKeys,
  settingsKeys,
  syncKeys,
  tenantProfileKeys,
  workspaceKeys,
}
