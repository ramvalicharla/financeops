import apiClient from "@/lib/api/client"

export interface PnLBreakdownRow {
  category: string
  account_code: string
  account_name: string
  amount: string
  debit_sum: string
  credit_sum: string
}

export interface PnLResult {
  org_entity_id: string
  from_date: string
  to_date: string
  revenue: string
  cost_of_sales: string
  gross_profit: string
  operating_expense: string
  operating_profit: string
  other_income: string
  other_expense: string
  net_profit: string
  breakdown: PnLBreakdownRow[]
}

export interface BalanceSheetItem {
  account_code: string
  account_name: string
  account_type: string
  sub_type: string | null
  amount: string
}

export interface BalanceSheetResult {
  org_entity_id: string
  as_of_date: string
  assets: BalanceSheetItem[]
  liabilities: BalanceSheetItem[]
  equity: BalanceSheetItem[]
  retained_earnings: string
  totals: {
    assets: string
    liabilities: string
    equity: string
    liabilities_and_equity: string
  }
}

export interface CashFlowBreakdownRow {
  category: string
  amount: string
}

export interface CashFlowResult {
  org_entity_id: string
  from_date: string
  to_date: string
  net_profit: string
  non_cash_adjustments: string
  working_capital_changes: string
  operating_cash_flow: string
  investing_cash_flow: string
  financing_cash_flow: string
  net_cash_flow: string
  breakdown: CashFlowBreakdownRow[]
}

export const getAccountingPnL = async (params: {
  org_entity_id: string
  from_date: string
  to_date: string
}): Promise<PnLResult> => {
  const query = new URLSearchParams({
    org_entity_id: params.org_entity_id,
    from_date: params.from_date,
    to_date: params.to_date,
  })
  const response = await apiClient.get<PnLResult>(
    `/api/v1/accounting/pnl?${query.toString()}`,
  )
  return response.data
}

export const getAccountingBalanceSheet = async (params: {
  org_entity_id: string
  as_of_date: string
}): Promise<BalanceSheetResult> => {
  const query = new URLSearchParams({
    org_entity_id: params.org_entity_id,
    as_of_date: params.as_of_date,
  })
  const response = await apiClient.get<BalanceSheetResult>(
    `/api/v1/accounting/balance-sheet?${query.toString()}`,
  )
  return response.data
}

export const getAccountingCashFlow = async (params: {
  org_entity_id: string
  from_date: string
  to_date: string
}): Promise<CashFlowResult> => {
  const query = new URLSearchParams({
    org_entity_id: params.org_entity_id,
    from_date: params.from_date,
    to_date: params.to_date,
  })
  const response = await apiClient.get<CashFlowResult>(
    `/api/v1/accounting/cash-flow?${query.toString()}`,
  )
  return response.data
}
