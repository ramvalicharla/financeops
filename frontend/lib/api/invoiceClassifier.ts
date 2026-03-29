import apiClient from "@/lib/api/client"

export type PaginatedResult<T> = {
  items: T[]
  total: number
  skip: number
  limit: number
  has_more: boolean
}

export type InvoiceClassificationType =
  | "FIXED_ASSET"
  | "PREPAID_EXPENSE"
  | "DIRECT_EXPENSE"
  | "CAPEX"
  | "OPEX"
  | "UNCERTAIN"

export type ClassificationMethod = "RULE_ENGINE" | "AI_GATEWAY" | "HUMAN_OVERRIDE"

export type InvoiceClassification = {
  id: string
  tenant_id: string
  entity_id: string
  invoice_number: string
  vendor_name: string | null
  invoice_date: string | null
  invoice_amount: string
  line_description: string | null
  classification: InvoiceClassificationType
  confidence: string
  classification_method: ClassificationMethod
  rule_matched: string | null
  ai_reasoning: string | null
  requires_human_review: boolean
  human_reviewed_by: string | null
  human_reviewed_at: string | null
  human_override: InvoiceClassificationType | null
  routing_action: string | null
  routed_record_id: string | null
  created_at: string
}

export type ClassificationRule = {
  id: string
  tenant_id: string
  rule_name: string
  description: string | null
  pattern_type: "VENDOR_NAME" | "DESCRIPTION_KEYWORD" | "AMOUNT_RANGE" | "VENDOR_AND_KEYWORD"
  pattern_value: string
  amount_min: string | null
  amount_max: string | null
  classification: InvoiceClassificationType
  confidence: string
  priority: number
  is_active: boolean
  created_at: string
  updated_at: string | null
}

export const classifyInvoice = async (payload: {
  entity_id: string
  invoice_number: string
  vendor_name: string
  invoice_date?: string | null
  invoice_amount: string
  line_description: string
}): Promise<InvoiceClassification> => {
  const response = await apiClient.post<InvoiceClassification>("/api/v1/invoice-classifier/classify", payload)
  return response.data
}

export const getReviewQueue = async (params: {
  entity_id: string
  skip?: number
  limit?: number
}): Promise<PaginatedResult<InvoiceClassification>> => {
  const skip = params.skip ?? 0
  const limit = params.limit ?? 20
  const response = await apiClient.get<PaginatedResult<InvoiceClassification>>(
    `/api/v1/invoice-classifier/queue?entity_id=${encodeURIComponent(params.entity_id)}&skip=${skip}&limit=${limit}`,
  )
  return response.data
}

export const reviewClassification = async (
  id: string,
  payload: { confirmed_classification: InvoiceClassificationType; notes?: string },
): Promise<InvoiceClassification> => {
  const response = await apiClient.post<InvoiceClassification>(`/api/v1/invoice-classifier/${id}/review`, payload)
  return response.data
}

export const routeClassification = async (
  id: string,
): Promise<{ routed_record_id: string; routing_action: string }> => {
  const response = await apiClient.post<{ routed_record_id: string; routing_action: string }>(
    `/api/v1/invoice-classifier/${id}/route`,
  )
  return response.data
}

export const listClassifications = async (params: {
  entity_id: string
  classification?: InvoiceClassificationType
  method?: ClassificationMethod
  skip?: number
  limit?: number
}): Promise<PaginatedResult<InvoiceClassification>> => {
  const search = new URLSearchParams()
  search.set("entity_id", params.entity_id)
  search.set("skip", String(params.skip ?? 0))
  search.set("limit", String(params.limit ?? 20))
  if (params.classification) {
    search.set("classification", params.classification)
  }
  if (params.method) {
    search.set("method", params.method)
  }
  const response = await apiClient.get<PaginatedResult<InvoiceClassification>>(
    `/api/v1/invoice-classifier?${search.toString()}`,
  )
  return response.data
}

export const listClassificationRules = async (): Promise<ClassificationRule[]> => {
  const response = await apiClient.get<ClassificationRule[]>("/api/v1/invoice-classifier/rules")
  return response.data
}

export const createClassificationRule = async (payload: {
  rule_name: string
  description?: string | null
  pattern_type: ClassificationRule["pattern_type"]
  pattern_value: string
  amount_min?: string | null
  amount_max?: string | null
  classification: InvoiceClassificationType
  confidence: string
  priority?: number
  is_active?: boolean
}): Promise<ClassificationRule> => {
  const response = await apiClient.post<ClassificationRule>("/api/v1/invoice-classifier/rules", payload)
  return response.data
}

export const updateClassificationRule = async (
  id: string,
  payload: Partial<{
    rule_name: string
    description: string | null
    pattern_type: ClassificationRule["pattern_type"]
    pattern_value: string
    amount_min: string | null
    amount_max: string | null
    classification: InvoiceClassificationType
    confidence: string
    priority: number
    is_active: boolean
  }>,
): Promise<ClassificationRule> => {
  const response = await apiClient.patch<ClassificationRule>(`/api/v1/invoice-classifier/rules/${id}`, payload)
  return response.data
}

export const deleteClassificationRule = async (id: string): Promise<ClassificationRule> => {
  const response = await apiClient.delete<ClassificationRule>(`/api/v1/invoice-classifier/rules/${id}`)
  return response.data
}
