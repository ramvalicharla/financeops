import apiClient from "@/lib/api/client"

export type FinanceModuleStatus = "ENABLED" | "DISABLED"

export type FinanceModuleRow = {
  module_name: string
  status: FinanceModuleStatus
  configuration_json: Record<string, unknown>
  updated_at: string
}

export type LeaseCreatePayload = {
  entity_id: string
  lease_start_date: string
  lease_end_date: string
  lease_payment: string
  discount_rate: string
  lease_type: string
  currency?: string
  rou_asset_account_code?: string
  lease_liability_account_code?: string
}

export type RevenueObligationPayload = {
  obligation_type: string
  allocation_value: string
}

export type RevenueCreatePayload = {
  entity_id: string
  customer_id: string
  contract_start_date: string
  contract_end_date: string
  contract_value: string
  obligations: RevenueObligationPayload[]
  receivable_account_code?: string
  revenue_account_code?: string
}

export type AssetCreatePayload = {
  entity_id: string
  asset_name: string
  cost: string
  useful_life_years: number
  depreciation_method: "SLM" | "WDV"
  residual_value?: string
  asset_account_code?: string
  payable_account_code?: string
}

export type PrepaidCreatePayload = {
  entity_id: string
  prepaid_name: string
  start_date: string
  end_date: string
  total_amount: string
  prepaid_account_code?: string
  cash_account_code?: string
}

export type AccrualCreatePayload = {
  entity_id: string
  accrual_name: string
  start_date: string
  end_date: string
  total_amount: string
  expense_account_code?: string
  accrued_liability_account_code?: string
}

export async function listFinanceModules(): Promise<FinanceModuleRow[]> {
  const { data } = await apiClient.get<FinanceModuleRow[]>("/api/v1/modules")
  return data
}

export async function setFinanceModuleStatus(
  moduleName: string,
  enabled: boolean,
): Promise<FinanceModuleRow> {
  const route = enabled
    ? `/api/v1/modules/${moduleName}/enable`
    : `/api/v1/modules/${moduleName}/disable`
  const { data } = await apiClient.post<FinanceModuleRow>(route, {})
  return data
}

export async function createLease(payload: LeaseCreatePayload) {
  const { data } = await apiClient.post("/api/v1/modules/lease/create", payload)
  return data
}

export async function getLeaseSchedule(leaseId: string) {
  const { data } = await apiClient.get("/api/v1/modules/lease/schedule", {
    params: { lease_id: leaseId },
  })
  return data
}

export async function createRevenueContract(payload: RevenueCreatePayload) {
  const { data } = await apiClient.post("/api/v1/modules/revenue/create-contract", payload)
  return data
}

export async function getRevenueSchedule(contractId: string) {
  const { data } = await apiClient.get("/api/v1/modules/revenue/schedule", {
    params: { contract_id: contractId },
  })
  return data
}

export async function createFixedAsset(payload: AssetCreatePayload) {
  const { data } = await apiClient.post("/api/v1/modules/assets/create", payload)
  return data
}

export async function getAssetSchedule(assetId: string) {
  const { data } = await apiClient.get("/api/v1/modules/assets/schedule", {
    params: { asset_id: assetId },
  })
  return data
}

export async function createPrepaidSchedule(payload: PrepaidCreatePayload) {
  const { data } = await apiClient.post("/api/v1/modules/prepaid/create", payload)
  return data
}

export async function createAccrualSchedule(payload: AccrualCreatePayload) {
  const { data } = await apiClient.post("/api/v1/modules/accrual/create", payload)
  return data
}

