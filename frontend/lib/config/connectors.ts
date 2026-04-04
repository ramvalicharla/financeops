import type { LucideIcon } from "lucide-react"
import { FileUp, Link as LinkIcon } from "lucide-react"
import type { ConnectorType, DatasetType } from "@/types/sync"

export type ConnectorCategory =
  | "OAuth"
  | "File Import"
  | "File / API"
  | "Desktop ERP"

export interface ConnectorDefinition {
  id: ConnectorType
  name: string
  description: string
  icon: LucideIcon
  category: ConnectorCategory
}

export const CONNECTOR_IDS = [
  "ZOHO",
  "TALLY",
  "BUSY",
  "MARG",
  "MUNIM",
  "QUICKBOOKS",
  "XERO",
  "GENERIC_FILE",
] as const satisfies readonly ConnectorType[]

export const DATASET_TYPES = [
  "TRIAL_BALANCE",
  "GENERAL_LEDGER",
  "BANK_STATEMENT",
  "ACCOUNTS_RECEIVABLE",
  "ACCOUNTS_PAYABLE",
  "INVOICE_REGISTER",
  "PURCHASE_REGISTER",
  "PAYROLL_SUMMARY",
  "CHART_OF_ACCOUNTS",
  "VENDOR_MASTER",
  "CUSTOMER_MASTER",
  "GST_RETURN_GSTR1",
  "FIXED_ASSET_REGISTER",
] as const satisfies readonly DatasetType[]

export const CONNECTORS = [
  {
    id: "ZOHO",
    name: "Zoho",
    description: "OAuth connector",
    icon: LinkIcon,
    category: "OAuth",
  },
  {
    id: "TALLY",
    name: "Tally",
    description: "File/XML import",
    icon: FileUp,
    category: "Desktop ERP",
  },
  {
    id: "BUSY",
    name: "Busy",
    description: "File/API key",
    icon: FileUp,
    category: "File / API",
  },
  {
    id: "MARG",
    name: "Marg",
    description: "File import",
    icon: FileUp,
    category: "Desktop ERP",
  },
  {
    id: "MUNIM",
    name: "Munim",
    description: "File import",
    icon: FileUp,
    category: "Desktop ERP",
  },
  {
    id: "QUICKBOOKS",
    name: "QuickBooks",
    description: "OAuth connector",
    icon: LinkIcon,
    category: "OAuth",
  },
  {
    id: "XERO",
    name: "Xero",
    description: "OAuth connector",
    icon: LinkIcon,
    category: "OAuth",
  },
  {
    id: "GENERIC_FILE",
    name: "Upload File",
    description: "CSV/JSON/XML/XLSX",
    icon: FileUp,
    category: "File Import",
  },
] as const satisfies readonly ConnectorDefinition[]

export const CONNECTOR_DATASETS = {
  ZOHO: [
    "TRIAL_BALANCE",
    "GENERAL_LEDGER",
    "BANK_STATEMENT",
    "ACCOUNTS_RECEIVABLE",
    "ACCOUNTS_PAYABLE",
    "INVOICE_REGISTER",
    "PURCHASE_REGISTER",
    "CHART_OF_ACCOUNTS",
    "VENDOR_MASTER",
    "CUSTOMER_MASTER",
    "GST_RETURN_GSTR1",
    "FIXED_ASSET_REGISTER",
  ],
  TALLY: [
    "TRIAL_BALANCE",
    "GENERAL_LEDGER",
    "INVOICE_REGISTER",
    "PURCHASE_REGISTER",
    "BANK_STATEMENT",
    "CHART_OF_ACCOUNTS",
    "VENDOR_MASTER",
    "CUSTOMER_MASTER",
    "GST_RETURN_GSTR1",
  ],
  BUSY: [
    "TRIAL_BALANCE",
    "GENERAL_LEDGER",
    "INVOICE_REGISTER",
    "PURCHASE_REGISTER",
    "BANK_STATEMENT",
    "CHART_OF_ACCOUNTS",
    "VENDOR_MASTER",
    "CUSTOMER_MASTER",
    "GST_RETURN_GSTR1",
  ],
  MARG: [
    "TRIAL_BALANCE",
    "GENERAL_LEDGER",
    "INVOICE_REGISTER",
    "PURCHASE_REGISTER",
    "CHART_OF_ACCOUNTS",
    "VENDOR_MASTER",
    "CUSTOMER_MASTER",
  ],
  MUNIM: [
    "TRIAL_BALANCE",
    "GENERAL_LEDGER",
    "INVOICE_REGISTER",
    "PURCHASE_REGISTER",
    "CHART_OF_ACCOUNTS",
    "VENDOR_MASTER",
    "CUSTOMER_MASTER",
  ],
  QUICKBOOKS: [
    "TRIAL_BALANCE",
    "GENERAL_LEDGER",
    "BANK_STATEMENT",
    "ACCOUNTS_RECEIVABLE",
    "ACCOUNTS_PAYABLE",
    "INVOICE_REGISTER",
    "PURCHASE_REGISTER",
    "CHART_OF_ACCOUNTS",
    "VENDOR_MASTER",
    "CUSTOMER_MASTER",
  ],
  XERO: [
    "TRIAL_BALANCE",
    "GENERAL_LEDGER",
    "BANK_STATEMENT",
    "ACCOUNTS_RECEIVABLE",
    "ACCOUNTS_PAYABLE",
    "INVOICE_REGISTER",
    "PURCHASE_REGISTER",
    "CHART_OF_ACCOUNTS",
    "VENDOR_MASTER",
    "CUSTOMER_MASTER",
  ],
  GENERIC_FILE: [
    "TRIAL_BALANCE",
    "GENERAL_LEDGER",
    "BANK_STATEMENT",
    "ACCOUNTS_RECEIVABLE",
    "ACCOUNTS_PAYABLE",
    "INVOICE_REGISTER",
    "PURCHASE_REGISTER",
    "PAYROLL_SUMMARY",
    "CHART_OF_ACCOUNTS",
    "VENDOR_MASTER",
    "CUSTOMER_MASTER",
    "GST_RETURN_GSTR1",
    "FIXED_ASSET_REGISTER",
  ],
} as const satisfies Record<ConnectorType, readonly DatasetType[]>
