import type { EntityType, ErpType } from "@/lib/api/orgSetup"

export const ORG_SETUP_STEP_NAMES = [
  "Org details",
  "Entity structure",
  "Chart of accounts",
  "Connect ERP",
  "Invite team",
] as const

export const CURRENCY_OPTIONS = ["INR", "USD", "SGD", "GBP", "EUR", "AED"] as const

export const COUNTRY_OPTIONS: Array<{ code: string; label: string }> = [
  { code: "IN", label: "India" },
  { code: "US", label: "United States" },
  { code: "SG", label: "Singapore" },
  { code: "GB", label: "United Kingdom" },
  { code: "AE", label: "United Arab Emirates" },
  { code: "DE", label: "Germany" },
]

export const ENTITY_TYPE_OPTIONS: Array<{ value: EntityType; label: string }> = [
  { value: "WHOLLY_OWNED_SUBSIDIARY", label: "Wholly owned subsidiary" },
  { value: "JOINT_VENTURE", label: "Joint venture" },
  { value: "ASSOCIATE", label: "Associate" },
  { value: "BRANCH", label: "Branch" },
  { value: "REPRESENTATIVE_OFFICE", label: "Representative office" },
  { value: "HOLDING_COMPANY", label: "Holding company" },
  { value: "PARTNERSHIP", label: "Partnership" },
  { value: "LLP", label: "LLP" },
  { value: "TRUST", label: "Trust" },
  { value: "SOLE_PROPRIETORSHIP", label: "Sole proprietorship" },
]

export const GAAP_OPTIONS = ["INDAS", "IFRS", "USGAAP", "MANAGEMENT"] as const

export const ERP_TYPE_OPTIONS: Array<{ value: ErpType; label: string; showVersion: boolean }> = [
  { value: "TALLY_PRIME", label: "Tally Prime", showVersion: true },
  { value: "TALLY_ERP9", label: "Tally ERP 9", showVersion: true },
  { value: "ZOHO_BOOKS", label: "Zoho Books", showVersion: false },
  { value: "QUICKBOOKS_ONLINE", label: "QuickBooks Online", showVersion: false },
  { value: "QUICKBOOKS_DESKTOP", label: "QuickBooks Desktop", showVersion: true },
  { value: "NETSUITE", label: "NetSuite", showVersion: false },
  { value: "SAP_B1", label: "SAP B1", showVersion: true },
  { value: "SAP_S4", label: "SAP S/4", showVersion: true },
  { value: "ORACLE_FUSION", label: "Oracle Fusion", showVersion: false },
  { value: "DYNAMICS_365", label: "Dynamics 365", showVersion: false },
  { value: "XERO", label: "Xero", showVersion: false },
  { value: "BUSY", label: "Busy", showVersion: false },
  { value: "MARG", label: "Marg", showVersion: false },
  { value: "MANUAL", label: "Manual", showVersion: false },
]

export const FISCAL_MONTHS: Array<{ value: number; label: string }> = [
  { value: 1, label: "January" },
  { value: 2, label: "February" },
  { value: 3, label: "March" },
  { value: 4, label: "April" },
  { value: 5, label: "May" },
  { value: 6, label: "June" },
  { value: 7, label: "July" },
  { value: 8, label: "August" },
  { value: 9, label: "September" },
  { value: 10, label: "October" },
  { value: 11, label: "November" },
  { value: 12, label: "December" },
]

export const deriveConsolidationMethod = (
  ownershipPct: string,
  entityType: EntityType,
): string => {
  const normalized = Number(ownershipPct)
  if (entityType === "JOINT_VENTURE") {
    return "Proportionate"
  }
  if (Number.isNaN(normalized)) {
    return "-"
  }
  if (normalized > 50) {
    return "Full consolidation"
  }
  if (normalized >= 20) {
    return "Equity method"
  }
  return "Excluded"
}
