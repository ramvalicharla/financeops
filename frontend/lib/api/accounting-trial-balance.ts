import apiClient from "@/lib/api/client"

export interface TrialBalanceRow {
  account_code: string
  account_name: string
  debit_sum: string
  credit_sum: string
  balance: string
}

export interface TrialBalanceResult {
  org_entity_id: string
  as_of_date: string
  from_date: string | null
  to_date: string | null
  total_debit: string
  total_credit: string
  rows: TrialBalanceRow[]
}

export const getAccountingTrialBalance = async (params: {
  org_entity_id: string
  as_of_date: string
  from_date?: string
  to_date?: string
}): Promise<TrialBalanceResult> => {
  const search = new URLSearchParams()
  search.set("org_entity_id", params.org_entity_id)
  search.set("as_of_date", params.as_of_date)
  if (params.from_date) search.set("from_date", params.from_date)
  if (params.to_date) search.set("to_date", params.to_date)

  const response = await apiClient.get<TrialBalanceResult>(
    `/api/v1/accounting/trial-balance?${search.toString()}`,
  )
  return response.data
}
