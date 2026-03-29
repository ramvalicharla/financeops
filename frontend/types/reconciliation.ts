export interface GLTBAccount {
  account_code: string
  account_name: string
  account_type: "ASSET" | "LIABILITY" | "EQUITY" | "REVENUE" | "EXPENSE"
  tb_balance: string
  gl_balance: string
  variance: string
  variance_pct: string
  status: "MATCHED" | "VARIANCE" | "MISSING_GL" | "MISSING_TB"
  journal_entries?: JournalEntry[]
}

export interface JournalEntry {
  entry_id: string
  date: string
  description: string
  debit: string
  credit: string
  reference: string | null
}

export interface GLTBReconResult {
  run_id: string
  entity_id: string
  period: string
  total_accounts: number
  matched_accounts: number
  variance_accounts: number
  total_variance: string
  accounts: GLTBAccount[]
  generated_at: string
}

export interface PayrollReconSummary {
  run_id: string
  entity_id: string
  period: string
  payroll_gross: string
  gl_gross: string
  gross_variance: string
  payroll_net: string
  gl_net: string
  net_variance: string
  payroll_deductions: string
  gl_deductions: string
  deductions_variance: string
  cost_centres: PayrollCostCentre[]
}

export interface PayrollCostCentre {
  cost_centre_id: string
  cost_centre_name: string
  payroll_amount: string
  gl_amount: string
  variance: string
  status: "MATCHED" | "VARIANCE"
  employees?: PayrollEmployee[]
}

export interface PayrollEmployee {
  employee_id: string
  employee_name: string
  gross_pay: string
  net_pay: string
  deductions: string
  gl_posting: string
  variance: string
}
