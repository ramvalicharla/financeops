import apiClient from "@/lib/api/client"

export type DecimalString = string

export interface CoaTemplate {
  id: string
  code: string
  name: string
  description: string | null
  is_active: boolean
}

export interface CoaHierarchyNode {
  id: string
  code: string
  name: string
  sort_order: number
}

export interface CoaHierarchyLedgerAccount extends CoaHierarchyNode {
  normal_balance: string
  cash_flow_tag: string | null
  bs_pl_flag: string | null
  asset_liability_class: string | null
}

export interface CoaHierarchySubgroup extends CoaHierarchyNode {
  ledger_accounts: CoaHierarchyLedgerAccount[]
}

export interface CoaHierarchyGroup extends CoaHierarchyNode {
  account_subgroups: CoaHierarchySubgroup[]
}

export interface CoaHierarchySubline extends CoaHierarchyNode {
  account_groups: CoaHierarchyGroup[]
}

export interface CoaHierarchyLineItem extends CoaHierarchyNode {
  sublines: CoaHierarchySubline[]
}

export interface CoaHierarchySchedule extends CoaHierarchyNode {
  gaap: string
  line_items: CoaHierarchyLineItem[]
}

export interface CoaHierarchyClassification extends CoaHierarchyNode {
  schedules: CoaHierarchySchedule[]
}

export interface CoaHierarchyResponse {
  template: {
    id: string
    code: string
    name: string
    description: string | null
  }
  classifications: CoaHierarchyClassification[]
}

export interface CoaLedgerAccount {
  id: string
  account_subgroup_id: string
  industry_template_id: string
  source_type: string
  tenant_id: string | null
  version: number
  code: string
  name: string
  description: string | null
  normal_balance: string
  cash_flow_tag: string | null
  cash_flow_method: string | null
  bs_pl_flag: string | null
  asset_liability_class: string | null
  is_monetary: boolean
  is_related_party: boolean
  is_tax_deductible: boolean
  is_control_account: boolean
  notes_reference: string | null
  is_active: boolean
  sort_order: number
  created_by: string | null
}

export type CoaUploadMode = "APPEND" | "REPLACE" | "VALIDATE_ONLY"

export interface CoaUploadError {
  row_number: number
  errors: string[]
}

export interface CoaUploadResult {
  batch_id: string
  upload_status: string
  total_rows: number
  valid_rows: number
  invalid_rows: number
  errors: CoaUploadError[]
}

export interface CoaValidationResult {
  total_rows: number
  valid_rows: number
  invalid_rows: number
  errors: CoaUploadError[]
}

export interface CoaApplyResult {
  batch_id: string
  applied_rows: number
  template_id: string
  source_type: string
}

export interface CoaSkipResult {
  coa_status: "pending" | "uploaded" | "skipped" | "erp_connected"
  next_step: number
  onboarding_score: number
}

export interface CoaUploadBatch {
  id: string
  tenant_id: string | null
  template_id: string | null
  source_type: string
  upload_mode: CoaUploadMode
  file_name: string
  upload_status: string
  error_log: Record<string, unknown> | null
  created_by: string | null
  created_at: string
  processed_at: string | null
}

export interface TenantCoaAccount {
  id: string
  tenant_id: string
  ledger_account_id: string | null
  parent_subgroup_id: string | null
  account_code: string
  display_name: string
  is_custom: boolean
  is_active: boolean
  sort_order: number | null
  platform_account_code: string | null
  platform_account_name: string | null
  bs_pl_flag: string | null
  asset_liability_class: string | null
  normal_balance: string | null
  hierarchy_path?: {
    schedule: string | null
    line_item: string | null
    subline: string | null
    group: string | null
    subgroup: string | null
  }
}

export interface ErpAccountInput {
  code: string
  name: string
  type?: string | null
}

export interface ErpMapping {
  id: string
  tenant_id: string
  entity_id: string
  erp_connector_type: string
  erp_account_code: string
  erp_account_name: string
  erp_account_type: string | null
  tenant_coa_account_id: string | null
  mapping_confidence: DecimalString | null
  is_auto_mapped: boolean
  is_confirmed: boolean
  confirmed_by: string | null
  confirmed_at: string | null
  is_active: boolean
}

export interface ErpMappingSummary {
  total: number
  mapped: number
  confirmed: number
  unmapped: number
  confidence_avg: DecimalString
}

export interface RawTBLineInput {
  erp_account_code: string
  erp_account_name: string
  debit_amount: DecimalString
  credit_amount: DecimalString
  currency: string
  period_start?: string | null
  period_end?: string | null
}

interface ReconTbRow {
  account_code: string
  account_name: string
  closing_balance: DecimalString
  currency: string
}

export interface ClassifiedTBLine {
  erp_account_code: string
  erp_account_name: string
  tenant_coa_account_id: string | null
  platform_account_code: string | null
  platform_account_name: string | null
  fs_classification: string | null
  fs_schedule: string | null
  fs_line_item: string | null
  fs_subline: string | null
  debit_amount: DecimalString
  credit_amount: DecimalString
  net_amount: DecimalString
  currency: string
  is_unmapped: boolean
  is_unconfirmed: boolean
}

export interface GlobalTBResponse {
  entity_results: Record<string, ClassifiedTBLine[]>
  consolidated: ClassifiedTBLine[]
  unmapped_lines: ClassifiedTBLine[]
  unconfirmed_lines: ClassifiedTBLine[]
  total_debits: DecimalString
  total_credits: DecimalString
  is_balanced: boolean
  unmapped_count: number
  unconfirmed_count: number
}

export const getCoaTemplates = async (): Promise<CoaTemplate[]> => {
  const response = await apiClient.get<CoaTemplate[]>("/api/v1/coa/templates")
  return response.data
}

export const getTemplateHierarchy = async (
  templateId: string,
): Promise<CoaHierarchyResponse> => {
  const response = await apiClient.get<CoaHierarchyResponse>(
    `/api/v1/coa/templates/${templateId}/hierarchy`,
  )
  return response.data
}

export const getTemplateAccounts = async (
  templateId: string,
): Promise<CoaLedgerAccount[]> => {
  const response = await apiClient.get<CoaLedgerAccount[]>(
    `/api/v1/coa/templates/${templateId}/accounts`,
  )
  return response.data
}

export const getEffectiveCoaAccounts = async (params: {
  template_id?: string
  group_code?: string
  subgroup_code?: string
  include_inactive?: boolean
} = {}): Promise<CoaLedgerAccount[]> => {
  const query = new URLSearchParams()
  if (params.template_id) {
    query.set("template_id", params.template_id)
  }
  if (params.group_code) {
    query.set("group_code", params.group_code)
  }
  if (params.subgroup_code) {
    query.set("subgroup_code", params.subgroup_code)
  }
  if (typeof params.include_inactive === "boolean") {
    query.set("include_inactive", String(params.include_inactive))
  }
  const suffix = query.toString() ? `?${query.toString()}` : ""
  const response = await apiClient.get<CoaLedgerAccount[]>(`/api/v1/coa/accounts${suffix}`)
  return response.data
}

export const uploadCoaFile = async (payload: {
  file: File
  template_id: string
  mode: CoaUploadMode
  origin_source?: string
  onboarding_step?: string
}): Promise<CoaUploadResult> => {
  const formData = new FormData()
  formData.append("file", payload.file)
  formData.append("template_id", payload.template_id)
  formData.append("mode", payload.mode)
  if (payload.origin_source) {
    formData.append("origin_source", payload.origin_source)
  }
  if (payload.onboarding_step) {
    formData.append("onboarding_step", payload.onboarding_step)
  }

  const response = await apiClient.post<CoaUploadResult>("/api/v1/coa/upload", formData)
  return response.data
}

export const validateCoaFile = async (
  file: File,
  options?: {
    origin_source?: string
    onboarding_step?: string
  },
): Promise<CoaValidationResult> => {
  const formData = new FormData()
  formData.append("file", file)
  if (options?.origin_source) {
    formData.append("origin_source", options.origin_source)
  }
  if (options?.onboarding_step) {
    formData.append("onboarding_step", options.onboarding_step)
  }
  const response = await apiClient.post<CoaValidationResult>("/api/v1/coa/validate", formData)
  return response.data
}

export const applyCoaBatch = async (batch_id: string): Promise<CoaApplyResult> => {
  const response = await apiClient.post<CoaApplyResult>("/api/v1/coa/apply", { batch_id })
  return response.data
}

export const skipCoaSetup = async (): Promise<CoaSkipResult> => {
  const response = await apiClient.post<CoaSkipResult>("/api/v1/coa/skip")
  return response.data
}

export const listCoaUploadBatches = async (limit = 50): Promise<CoaUploadBatch[]> => {
  const response = await apiClient.get<CoaUploadBatch[]>(
    `/api/v1/coa/upload/batches?limit=${limit}`,
  )
  return response.data
}

export const getFsClassifications = async (): Promise<
  Array<{ id: string; code: string; name: string; sort_order: number }>
> => {
  const response = await apiClient.get<
    Array<{ id: string; code: string; name: string; sort_order: number }>
  >("/api/v1/coa/fs-classifications")
  return response.data
}

export const getFsSchedules = async (
  gaap: string,
): Promise<Array<{ id: string; code: string; name: string; gaap: string }>> => {
  const response = await apiClient.get<
    Array<{ id: string; code: string; name: string; gaap: string }>
  >(`/api/v1/coa/fs-schedules?gaap=${encodeURIComponent(gaap)}`)
  return response.data
}

export const initialiseTenantCoa = async (
  templateId: string,
): Promise<{ initialised: boolean }> => {
  const response = await apiClient.post<{ initialised: boolean }>(
    "/api/v1/coa/tenant/initialise",
    { template_id: templateId },
  )
  return response.data
}

export const getTenantCoaAccounts = async (): Promise<TenantCoaAccount[]> => {
  const response = await apiClient.get<TenantCoaAccount[]>("/api/v1/coa/tenant/accounts")
  return response.data
}

export const addTenantCustomAccount = async (
  payload: Pick<TenantCoaAccount, "parent_subgroup_id" | "account_code" | "display_name">,
): Promise<TenantCoaAccount> => {
  const response = await apiClient.post<TenantCoaAccount>("/api/v1/coa/tenant/accounts", payload)
  return response.data
}

export const updateTenantAccount = async (
  accountId: string,
  payload: { display_name?: string; is_active?: boolean },
): Promise<TenantCoaAccount> => {
  const response = await apiClient.patch<TenantCoaAccount>(
    `/api/v1/coa/tenant/accounts/${accountId}`,
    payload,
  )
  return response.data
}

export const getTenantAccount = async (
  accountId: string,
): Promise<TenantCoaAccount> => {
  const response = await apiClient.get<TenantCoaAccount>(
    `/api/v1/coa/tenant/accounts/${accountId}`,
  )
  return response.data
}

export const autoSuggestErpMappings = async (payload: {
  entity_id: string
  erp_connector_type: string
  erp_accounts: ErpAccountInput[]
}): Promise<ErpMapping[]> => {
  const response = await apiClient.post<ErpMapping[]>(
    "/api/v1/coa/erp-mappings/auto-suggest",
    payload,
  )
  return response.data
}

export const getErpMappings = async (payload: {
  entity_id: string
  erp_connector_type?: string
  is_confirmed?: boolean
}): Promise<ErpMapping[]> => {
  const params = new URLSearchParams({ entity_id: payload.entity_id })
  if (payload.erp_connector_type) {
    params.set("erp_connector_type", payload.erp_connector_type)
  }
  if (typeof payload.is_confirmed === "boolean") {
    params.set("is_confirmed", String(payload.is_confirmed))
  }
  const response = await apiClient.get<ErpMapping[]>(`/api/v1/coa/erp-mappings?${params.toString()}`)
  return response.data
}

export const confirmErpMapping = async (
  mappingId: string,
  tenantCoaAccountId: string,
): Promise<ErpMapping> => {
  const response = await apiClient.patch<ErpMapping>(
    `/api/v1/coa/erp-mappings/${mappingId}/confirm`,
    { tenant_coa_account_id: tenantCoaAccountId },
  )
  return response.data
}

export const bulkConfirmErpMappings = async (payload: {
  mapping_ids: string[]
  auto_confirm_above?: string
}): Promise<{ confirmed_count: number }> => {
  const response = await apiClient.post<{ confirmed_count: number }>(
    "/api/v1/coa/erp-mappings/bulk-confirm",
    payload,
  )
  return response.data
}

export const getErpMappingSummary = async (payload: {
  entity_id: string
  erp_connector_type?: string
}): Promise<ErpMappingSummary> => {
  const params = new URLSearchParams({ entity_id: payload.entity_id })
  if (payload.erp_connector_type) {
    params.set("erp_connector_type", payload.erp_connector_type)
  }
  const response = await apiClient.get<ErpMappingSummary>(
    `/api/v1/coa/erp-mappings/summary?${params.toString()}`,
  )
  return response.data
}

export const getUnmappedErpMappings = async (payload: {
  entity_id: string
  erp_connector_type?: string
}): Promise<ErpMapping[]> => {
  const params = new URLSearchParams({ entity_id: payload.entity_id })
  if (payload.erp_connector_type) {
    params.set("erp_connector_type", payload.erp_connector_type)
  }
  const response = await apiClient.get<ErpMapping[]>(
    `/api/v1/coa/erp-mappings/unmapped?${params.toString()}`,
  )
  return response.data
}

export const classifyTrialBalance = async (payload: {
  entity_id: string
  gaap?: string
  raw_tb: RawTBLineInput[]
}): Promise<GlobalTBResponse> => {
  const response = await apiClient.post<GlobalTBResponse>(
    "/api/v1/coa/trial-balance/classify",
    payload,
  )
  return response.data
}

export const pullRawTrialBalance = async (payload: {
  period_year?: number
  period_month?: number
  entity_name?: string
  limit?: number
  offset?: number
  period_start?: string
  period_end?: string
}): Promise<RawTBLineInput[]> => {
  const params = new URLSearchParams()
  if (payload.period_year) {
    params.set("period_year", String(payload.period_year))
  }
  if (payload.period_month) {
    params.set("period_month", String(payload.period_month))
  }
  if (payload.entity_name) {
    params.set("entity_name", payload.entity_name)
  }
  params.set("limit", String(payload.limit ?? 1000))
  params.set("offset", String(payload.offset ?? 0))
  const response = await apiClient.get<{ rows: ReconTbRow[] }>(
    `/api/v1/recon/tb-rows?${params.toString()}`,
  )
  return (response.data.rows ?? []).map((row) => {
    const normalized = (row.closing_balance ?? "0").trim()
    const isNegative = normalized.startsWith("-")
    const absoluteValue = isNegative ? normalized.slice(1) : normalized
    return {
      erp_account_code: row.account_code,
      erp_account_name: row.account_name,
      debit_amount: isNegative ? "0" : absoluteValue,
      credit_amount: isNegative ? absoluteValue : "0",
      currency: row.currency ?? "INR",
      period_start: payload.period_start ?? null,
      period_end: payload.period_end ?? null,
    }
  })
}

export const classifyMultiEntityTrialBalance = async (payload: {
  gaap?: string
  entity_raw_tbs: Record<string, RawTBLineInput[]>
}): Promise<GlobalTBResponse> => {
  const response = await apiClient.post<GlobalTBResponse>(
    "/api/v1/coa/trial-balance/classify-multi-entity",
    payload,
  )
  return response.data
}

export const exportTrialBalance = async (payload: {
  entity_id: string
  gaap?: string
  format: "csv" | "xlsx"
  raw_tb: RawTBLineInput[]
}): Promise<Blob> => {
  const params = new URLSearchParams({
    entity_id: payload.entity_id,
    gaap: payload.gaap ?? "INDAS",
    format: payload.format,
  })
  const response = await apiClient.request<Blob>({
    url: `/api/v1/coa/trial-balance/export?${params.toString()}`,
    method: "GET",
    data: payload.raw_tb,
    responseType: "blob",
  })
  return response.data
}
