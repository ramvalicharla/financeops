import apiClient from "@/lib/api/client"

export type CoaStatus = "pending" | "uploaded" | "skipped" | "erp_connected"

export interface OrgSetupProgress {
  id: string
  tenant_id: string
  current_step: number
  step1_data: Record<string, unknown> | null
  step2_data: Record<string, unknown> | null
  step3_data: Record<string, unknown> | null
  step4_data: Record<string, unknown> | null
  step5_data: Record<string, unknown> | null
  step6_data: Record<string, unknown> | null
  coa_status: CoaStatus
  onboarding_score: number
  completed_at: string | null
  created_at: string
  updated_at: string | null
}

export interface OrgGroup {
  id: string
  tenant_id: string
  group_name: string
  country_of_incorp: string
  country_code: string
  functional_currency: string
  reporting_currency: string
  logo_url: string | null
  website: string | null
  created_at: string
  updated_at: string | null
}

export interface ReviewRow {
  label: string
  value: string
}

export interface SetupIntentDraft<TStep extends string = string> {
  draft_id: string
  step: TStep
  status: "draft"
  review_rows: ReviewRow[]
  payload: Record<string, unknown>
}

export type EntityType =
  | "WHOLLY_OWNED_SUBSIDIARY"
  | "JOINT_VENTURE"
  | "ASSOCIATE"
  | "BRANCH"
  | "REPRESENTATIVE_OFFICE"
  | "HOLDING_COMPANY"
  | "PARTNERSHIP"
  | "LLP"
  | "TRUST"
  | "SOLE_PROPRIETORSHIP"

export type ApplicableGaap = "INDAS" | "IFRS" | "USGAAP" | "MANAGEMENT"

export type ErpType =
  | "TALLY_PRIME"
  | "TALLY_ERP9"
  | "ZOHO_BOOKS"
  | "QUICKBOOKS_ONLINE"
  | "QUICKBOOKS_DESKTOP"
  | "NETSUITE"
  | "SAP_B1"
  | "SAP_S4"
  | "ORACLE_FUSION"
  | "DYNAMICS_365"
  | "XERO"
  | "BUSY"
  | "MARG"
  | "MANUAL"

export interface OrgEntity {
  id: string
  tenant_id: string
  org_group_id: string
  cp_entity_id: string | null
  legal_name: string
  display_name: string | null
  entity_type: EntityType
  country_code: string
  state_code: string | null
  functional_currency: string
  reporting_currency: string
  fiscal_year_start: number
  applicable_gaap: ApplicableGaap
  industry_template_id: string | null
  incorporation_number: string | null
  pan: string | null
  tan: string | null
  cin: string | null
  gstin: string | null
  lei: string | null
  tax_jurisdiction: string | null
  tax_rate: string | null
  is_active: boolean
  created_at: string
  updated_at: string | null
}

export interface OrgOwnership {
  id: string
  tenant_id: string
  parent_entity_id: string
  child_entity_id: string
  ownership_pct: string
  consolidation_method: string
  effective_from: string
  effective_to: string | null
  notes: string | null
  created_at: string
}

export interface OrgEntityErpConfig {
  id: string
  tenant_id: string
  org_entity_id: string
  erp_type: ErpType
  erp_version: string | null
  connection_config: Record<string, unknown> | null
  is_primary: boolean
  connection_tested: boolean
  connection_tested_at: string | null
  is_active: boolean
  created_at: string
  updated_at: string | null
}

export interface EntityTemplateSummary {
  entity_id: string
  template_code: string
  account_count: number
}

export interface Step5Response {
  initialised_count: number
  entity_summaries: EntityTemplateSummary[]
  coa_status: CoaStatus
  onboarding_score: number
}

export interface Step6Response {
  confirmed_count: number
  unmapped_count: number
  setup_complete: boolean
  coa_status: CoaStatus
  onboarding_score: number
}

export interface OwnershipTreeNode {
  entity_id: string
  legal_name: string
  display_name: string | null
  entity_type: string
  ownership_pct: string | null
  consolidation_method: string | null
  children: OwnershipTreeNode[]
}

export interface OwnershipTree {
  group_id: string | null
  group_name: string | null
  entities: OwnershipTreeNode[]
}

export interface OrgSetupSummary {
  group: OrgGroup | null
  entities: OrgEntity[]
  ownership: OrgOwnership[]
  erp_configs: OrgEntityErpConfig[]
  current_step: number
  completed_at: string | null
  coa_account_count: number
  coa_status: CoaStatus
  onboarding_score: number
  mapping_summary: {
    total: number
    mapped: number
    confirmed: number
    unmapped: number
    confidence_avg: string
  }
}

export interface Step1Payload {
  group_name: string
  country_of_incorp: string
  country_code: string
  functional_currency: string
  reporting_currency: string
  logo_url?: string | null
  website?: string | null
}

export interface Step2EntityPayload {
  legal_name: string
  display_name?: string | null
  entity_type: EntityType
  country_code: string
  state_code?: string | null
  functional_currency: string
  reporting_currency: string
  fiscal_year_start: number
  applicable_gaap: ApplicableGaap
  incorporation_number?: string | null
  pan?: string | null
  tan?: string | null
  cin?: string | null
  gstin?: string | null
  lei?: string | null
  tax_jurisdiction?: string | null
  tax_rate?: string | null
}

export interface Step1ConfirmResponse {
  draft_id: string
  step: "create_organization"
  status: "confirmed"
  review_rows: ReviewRow[]
  group: OrgGroup
}

export interface Step2ConfirmResponse {
  draft_id: string
  step: "create_entity"
  status: "confirmed"
  review_rows: ReviewRow[]
  entities: OrgEntity[]
}

export interface ModuleSelectionReview {
  draft_id: string
  step: "review_module_selection"
  status: "draft"
  review_rows: ReviewRow[]
  payload: {
    module_names: string[]
    tenant_id: string
  }
  review_only: true
}

export interface OwnershipPayload {
  parent_entity_id: string
  child_entity_id: string
  ownership_pct: string
  manual_consolidation_method?: string | null
  effective_from: string
  notes?: string | null
}

export interface ErpConfigPayload {
  org_entity_id: string
  erp_type: ErpType
  erp_version?: string | null
  is_primary: boolean
}

export interface EntityTemplatePayload {
  entity_id: string
  template_id: string
}

export const getOrgSetupProgress = async (): Promise<OrgSetupProgress> => {
  const response = await apiClient.get<OrgSetupProgress>("/api/v1/org-setup/progress")
  return response.data
}

export const submitOrgSetupStep1 = async (payload: Step1Payload): Promise<OrgGroup> => {
  const response = await apiClient.post<{ group: OrgGroup }>("/api/v1/org-setup/step1", payload)
  return response.data.group
}

export const createOrgSetupStep1Draft = async (
  payload: Step1Payload,
): Promise<SetupIntentDraft<"create_organization">> => {
  const response = await apiClient.post<SetupIntentDraft<"create_organization">>(
    "/api/v1/org-setup/step1/draft",
    payload,
  )
  return response.data
}

export const confirmOrgSetupStep1Draft = async (
  draftId: string,
): Promise<Step1ConfirmResponse> => {
  const response = await apiClient.post<Step1ConfirmResponse>(
    "/api/v1/org-setup/step1/confirm",
    { draft_id: draftId },
  )
  return response.data
}

export const submitOrgSetupStep2 = async (payload: {
  group_id: string
  entities: Step2EntityPayload[]
}): Promise<OrgEntity[]> => {
  const response = await apiClient.post<{ entities: OrgEntity[] }>("/api/v1/org-setup/step2", payload)
  return response.data.entities
}

export const createOrgSetupStep2Draft = async (payload: {
  group_id: string
  entities: Step2EntityPayload[]
}): Promise<SetupIntentDraft<"create_entity">> => {
  const response = await apiClient.post<SetupIntentDraft<"create_entity">>(
    "/api/v1/org-setup/step2/draft",
    payload,
  )
  return response.data
}

export const confirmOrgSetupStep2Draft = async (
  draftId: string,
): Promise<Step2ConfirmResponse> => {
  const response = await apiClient.post<Step2ConfirmResponse>(
    "/api/v1/org-setup/step2/confirm",
    { draft_id: draftId },
  )
  return response.data
}

export const reviewOrgSetupModuleSelection = async (payload: {
  module_names: string[]
}): Promise<ModuleSelectionReview> => {
  const response = await apiClient.post<ModuleSelectionReview>(
    "/api/v1/org-setup/step3/modules/review",
    payload,
  )
  return response.data
}

export const submitOrgSetupStep3 = async (payload: {
  relationships: OwnershipPayload[]
}): Promise<OrgOwnership[]> => {
  const response = await apiClient.post<{ ownership: OrgOwnership[] }>("/api/v1/org-setup/step3", payload)
  return response.data.ownership
}

export const submitOrgSetupStep4 = async (payload: {
  configs: ErpConfigPayload[]
}): Promise<OrgEntityErpConfig[]> => {
  const response = await apiClient.post<{ configs: OrgEntityErpConfig[] }>("/api/v1/org-setup/step4", payload)
  return response.data.configs
}

export const submitOrgSetupStep5 = async (payload: {
  entity_templates: EntityTemplatePayload[]
}): Promise<Step5Response> => {
  const response = await apiClient.post<Step5Response>("/api/v1/org-setup/step5", payload)
  return response.data
}

export const submitOrgSetupStep6 = async (payload: {
  confirmed_mapping_ids: string[]
  auto_confirm_above?: string
}): Promise<Step6Response> => {
  const response = await apiClient.post<Step6Response>("/api/v1/org-setup/step6", payload)
  return response.data
}

export const getOrgSetupSummary = async (): Promise<OrgSetupSummary> => {
  const response = await apiClient.get<OrgSetupSummary>("/api/v1/org-setup/summary")
  return response.data
}

export const listOrgEntities = async (): Promise<OrgEntity[]> => {
  const response = await apiClient.get<OrgEntity[]>("/api/v1/org-setup/entities")
  return response.data
}

export const getOrgEntity = async (entityId: string): Promise<OrgEntity> => {
  const response = await apiClient.get<OrgEntity>(`/api/v1/org-setup/entities/${entityId}`)
  return response.data
}

export const getOwnershipTree = async (): Promise<OwnershipTree> => {
  const response = await apiClient.get<OwnershipTree>("/api/v1/org-setup/ownership-tree")
  return response.data
}

export const updateOrgEntity = async (
  entityId: string,
  payload: Partial<Omit<OrgEntity, "id" | "tenant_id" | "org_group_id" | "cp_entity_id" | "created_at" | "updated_at">>,
): Promise<OrgEntity> => {
  const response = await apiClient.patch<OrgEntity>(`/api/v1/org-setup/entities/${entityId}`, payload)
  return response.data
}
