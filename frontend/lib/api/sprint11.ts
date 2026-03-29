import apiClient from "@/lib/api/client"
import type { DisplayScale } from "@/lib/utils"
import type {
  AuditorPortalAccess,
  AuditorRequest,
  CovenantDashboard,
  CovenantEvent,
  ForecastRun,
  ForecastSummary,
  ForecastWeek,
  GAAPComparison,
  GAAPConfig,
  GAAPRun,
  ICTransaction,
  PBCTracker,
  PaginatedResult,
  SignoffCertificatePayload,
  SignoffRecord,
  StatutoryCalendarItem,
  StatutoryFiling,
  StatutoryRegisterEntry,
  TaxPosition,
  TaxProvisionRun,
  TaxSchedule,
  TransferPricingApplicability,
  TransferPricingDoc,
} from "@/lib/types/sprint11"

export const listTreasuryForecasts = async (params?: {
  limit?: number
  offset?: number
}): Promise<PaginatedResult<ForecastRun>> => {
  const search = new URLSearchParams()
  search.set("limit", String(params?.limit ?? 20))
  search.set("offset", String(params?.offset ?? 0))
  const response = await apiClient.get<PaginatedResult<ForecastRun>>(
    `/api/v1/treasury/forecasts?${search.toString()}`,
  )
  return response.data
}

export const createTreasuryForecast = async (payload: {
  run_name: string
  base_date: string
  opening_cash_balance: string
  currency?: string
  weeks?: number
  seed_historical?: boolean
}): Promise<{
  run: ForecastRun
  summary: {
    closing_balance_week_13: string
    minimum_balance: string
    minimum_balance_week: number
    is_cash_positive: boolean
  }
}> => {
  const response = await apiClient.post<{
    run: ForecastRun
    summary: {
      closing_balance_week_13: string
      minimum_balance: string
      minimum_balance_week: number
      is_cash_positive: boolean
    }
  }>("/api/v1/treasury/forecasts", payload)
  return response.data
}

export const getTreasuryForecast = async (id: string): Promise<ForecastSummary> => {
  const response = await apiClient.get<ForecastSummary>(`/api/v1/treasury/forecasts/${id}`)
  return response.data
}

export const updateTreasuryWeek = async (
  forecastId: string,
  weekNumber: number,
  updates: Partial<
    Pick<
      ForecastWeek,
      | "customer_collections"
      | "other_inflows"
      | "supplier_payments"
      | "payroll"
      | "rent_and_utilities"
      | "loan_repayments"
      | "tax_payments"
      | "capex"
      | "other_outflows"
      | "notes"
    >
  >,
): Promise<ForecastWeek> => {
  const response = await apiClient.patch<ForecastWeek>(
    `/api/v1/treasury/forecasts/${forecastId}/weeks/${weekNumber}`,
    updates,
  )
  return response.data
}

export const publishTreasuryForecast = async (
  forecastId: string,
): Promise<{ id: string; status: string; is_published: boolean }> => {
  const response = await apiClient.post<{ id: string; status: string; is_published: boolean }>(
    `/api/v1/treasury/forecasts/${forecastId}/publish`,
  )
  return response.data
}

export const getTaxSchedule = async (fiscalYear: number): Promise<TaxSchedule> => {
  const response = await apiClient.get<TaxSchedule>(
    `/api/v1/tax/schedule?fiscal_year=${fiscalYear}`,
  )
  return response.data
}

export interface DisplayPreferencesPayload {
  effective_scale: DisplayScale
  user_override: DisplayScale | null
  tenant_default: DisplayScale
  currency: string
  locale: string
  scale_label: string
}

export const getDisplayPreferences = async (): Promise<DisplayPreferencesPayload> => {
  const response = await apiClient.get<DisplayPreferencesPayload>(
    "/api/v1/tenants/display-preferences",
  )
  return response.data
}

export const updateDisplayPreferences = async (payload: {
  user_scale?: DisplayScale
  tenant_scale?: DisplayScale
}): Promise<{ message: string }> => {
  const response = await apiClient.patch<{ message: string }>(
    "/api/v1/tenants/display-preferences",
    payload,
  )
  return response.data
}

export const getTaxProvision = async (period: string): Promise<TaxProvisionRun> => {
  const response = await apiClient.get<TaxProvisionRun>(`/api/v1/tax/provision/${period}`)
  return response.data
}

export const computeTaxProvision = async (payload: {
  period: string
  entity_id?: string | null
  applicable_tax_rate: string
  tax_rate_description?: string
}): Promise<TaxProvisionRun> => {
  const response = await apiClient.post<TaxProvisionRun>("/api/v1/tax/provision/compute", payload)
  return response.data
}

export const listTaxPositions = async (params?: {
  limit?: number
  offset?: number
}): Promise<PaginatedResult<TaxPosition>> => {
  const search = new URLSearchParams()
  search.set("limit", String(params?.limit ?? 100))
  search.set("offset", String(params?.offset ?? 0))
  const response = await apiClient.get<PaginatedResult<TaxPosition>>(
    `/api/v1/tax/positions?${search.toString()}`,
  )
  return response.data
}

export const getCovenantDashboard = async (): Promise<CovenantDashboard> => {
  const response = await apiClient.get<CovenantDashboard>("/api/v1/covenants/dashboard")
  return response.data
}

export const runCovenantCheck = async (period: string): Promise<{ events: CovenantEvent[]; count: number }> => {
  const response = await apiClient.post<{ events: CovenantEvent[]; count: number }>(
    "/api/v1/covenants/check",
    { period },
  )
  return response.data
}

export const getTransferPricingApplicability = async (
  fiscalYear: number,
): Promise<TransferPricingApplicability> => {
  const response = await apiClient.get<TransferPricingApplicability>(
    `/api/v1/transfer-pricing/applicability?fiscal_year=${fiscalYear}`,
  )
  return response.data
}

export const listICTransactions = async (params?: {
  fiscal_year?: number
  limit?: number
  offset?: number
}): Promise<PaginatedResult<ICTransaction>> => {
  const search = new URLSearchParams()
  if (params?.fiscal_year !== undefined) {
    search.set("fiscal_year", String(params.fiscal_year))
  }
  search.set("limit", String(params?.limit ?? 100))
  search.set("offset", String(params?.offset ?? 0))
  const response = await apiClient.get<PaginatedResult<ICTransaction>>(
    `/api/v1/transfer-pricing/transactions?${search.toString()}`,
  )
  return response.data
}

export const addICTransaction = async (payload: {
  fiscal_year: number
  transaction_type: string
  related_party_name: string
  related_party_country: string
  transaction_amount: string
  currency?: string
  pricing_method: string
  is_international?: boolean
  arm_length_price?: string | null
  actual_price?: string | null
  description?: string | null
}): Promise<ICTransaction> => {
  const response = await apiClient.post<ICTransaction>("/api/v1/transfer-pricing/transactions", payload)
  return response.data
}

export const generateForm3CEB = async (fiscalYear: number): Promise<TransferPricingDoc> => {
  const response = await apiClient.post<TransferPricingDoc>("/api/v1/transfer-pricing/generate-3ceb", {
    fiscal_year: fiscalYear,
  })
  return response.data
}

export const listTransferPricingDocs = async (params?: {
  limit?: number
  offset?: number
}): Promise<PaginatedResult<TransferPricingDoc>> => {
  const search = new URLSearchParams()
  search.set("limit", String(params?.limit ?? 100))
  search.set("offset", String(params?.offset ?? 0))
  const response = await apiClient.get<PaginatedResult<TransferPricingDoc>>(
    `/api/v1/transfer-pricing/documents?${search.toString()}`,
  )
  return response.data
}

export const getTransferPricingDoc = async (documentId: string): Promise<TransferPricingDoc> => {
  const response = await apiClient.get<TransferPricingDoc>(
    `/api/v1/transfer-pricing/documents/${documentId}`,
  )
  return response.data
}

export const listSignoffs = async (params?: {
  limit?: number
  offset?: number
}): Promise<PaginatedResult<SignoffRecord>> => {
  const search = new URLSearchParams()
  search.set("limit", String(params?.limit ?? 100))
  search.set("offset", String(params?.offset ?? 0))
  const response = await apiClient.get<PaginatedResult<SignoffRecord>>(
    `/api/v1/signoff?${search.toString()}`,
  )
  return response.data
}

export const signoffSign = async (
  signoffId: string,
  totpCode: string,
): Promise<SignoffRecord> => {
  const response = await apiClient.post<SignoffRecord>(`/api/v1/signoff/${signoffId}/sign`, {
    totp_code: totpCode,
  })
  return response.data
}

export const getSignoffCertificate = async (
  signoffId: string,
): Promise<SignoffCertificatePayload> => {
  const response = await apiClient.get<SignoffCertificatePayload>(
    `/api/v1/signoff/${signoffId}/certificate`,
  )
  return response.data
}

export const verifySignoff = async (
  signoffId: string,
  contentHash: string,
): Promise<{ is_valid: boolean }> => {
  const response = await apiClient.post<{ is_valid: boolean }>(
    `/api/v1/signoff/${signoffId}/verify`,
    { content_hash: contentHash },
  )
  return response.data
}

export const getStatutoryCalendar = async (
  fiscalYear: number,
): Promise<StatutoryCalendarItem[]> => {
  const response = await apiClient.get<StatutoryCalendarItem[]>(
    `/api/v1/statutory/calendar?fiscal_year=${fiscalYear}`,
  )
  return response.data
}

export const listStatutoryFilings = async (params?: {
  status?: string
  fiscal_year?: number
  limit?: number
  offset?: number
}): Promise<PaginatedResult<StatutoryFiling>> => {
  const search = new URLSearchParams()
  if (params?.status) {
    search.set("status", params.status)
  }
  if (params?.fiscal_year !== undefined) {
    search.set("fiscal_year", String(params.fiscal_year))
  }
  search.set("limit", String(params?.limit ?? 50))
  search.set("offset", String(params?.offset ?? 0))
  const response = await apiClient.get<PaginatedResult<StatutoryFiling>>(
    `/api/v1/statutory/filings?${search.toString()}`,
  )
  return response.data
}

export const markStatutoryFiled = async (
  filingId: string,
  payload: { filed_date: string; filing_reference: string },
): Promise<StatutoryFiling> => {
  const response = await apiClient.post<StatutoryFiling>(
    `/api/v1/statutory/filings/${filingId}/file`,
    payload,
  )
  return response.data
}

export const getStatutoryRegister = async (
  registerType: string,
  params?: { limit?: number; offset?: number },
): Promise<PaginatedResult<StatutoryRegisterEntry>> => {
  const search = new URLSearchParams()
  search.set("limit", String(params?.limit ?? 50))
  search.set("offset", String(params?.offset ?? 0))
  const response = await apiClient.get<PaginatedResult<StatutoryRegisterEntry>>(
    `/api/v1/statutory/registers/${registerType}?${search.toString()}`,
  )
  return response.data
}

export const addStatutoryRegisterEntry = async (
  registerType: string,
  payload: {
    entry_date: string
    entry_description: string
    folio_number?: string | null
    amount?: string | null
    currency?: string | null
    reference_document?: string | null
  },
): Promise<StatutoryRegisterEntry> => {
  const response = await apiClient.post<StatutoryRegisterEntry>(
    `/api/v1/statutory/registers/${registerType}`,
    payload,
  )
  return response.data
}

export const getGAAPConfig = async (): Promise<GAAPConfig> => {
  const response = await apiClient.get<GAAPConfig>("/api/v1/gaap/config")
  return response.data
}

export const getGAAPComparison = async (period: string): Promise<GAAPComparison> => {
  const response = await apiClient.get<GAAPComparison>(`/api/v1/gaap/comparison?period=${period}`)
  return response.data
}

export const computeGAAP = async (
  period: string,
  gaapFramework: string,
): Promise<GAAPRun> => {
  const response = await apiClient.post<GAAPRun>("/api/v1/gaap/compute", {
    period,
    gaap_framework: gaapFramework,
  })
  return response.data
}

export const listAuditorAccess = async (params?: {
  limit?: number
  offset?: number
}): Promise<PaginatedResult<AuditorPortalAccess>> => {
  const search = new URLSearchParams()
  search.set("limit", String(params?.limit ?? 50))
  search.set("offset", String(params?.offset ?? 0))
  const response = await apiClient.get<PaginatedResult<AuditorPortalAccess>>(
    `/api/v1/audit/access?${search.toString()}`,
  )
  return response.data
}

export const grantAuditorAccess = async (payload: {
  auditor_email: string
  auditor_firm: string
  engagement_name: string
  valid_from: string
  valid_until: string
  modules_accessible: string[]
  access_level?: string
}): Promise<{ access: AuditorPortalAccess; token: string }> => {
  const response = await apiClient.post<{ access: AuditorPortalAccess; token: string }>(
    "/api/v1/audit/access/grant",
    payload,
  )
  return response.data
}

export const revokeAuditorAccess = async (
  accessId: string,
): Promise<AuditorPortalAccess> => {
  const response = await apiClient.patch<AuditorPortalAccess>(`/api/v1/audit/access/${accessId}/revoke`)
  return response.data
}

export const getPBCTracker = async (engagementId: string): Promise<PBCTracker> => {
  const response = await apiClient.get<PBCTracker>(`/api/v1/audit/${engagementId}/pbc`)
  return response.data
}

export const respondToPBCRequest = async (
  engagementId: string,
  requestId: string,
  payload: {
    status: string
    response_notes?: string | null
    evidence_urls?: string[]
  },
): Promise<AuditorRequest> => {
  const response = await apiClient.post<AuditorRequest>(
    `/api/v1/audit/${engagementId}/requests/${requestId}/respond`,
    payload,
  )
  return response.data
}
