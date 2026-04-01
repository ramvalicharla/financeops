import apiClient from "@/lib/api/client"
import type {
  ConsolidationRunAcceptedResponse,
  ConsolidationRunDetailsResponse,
  ConsolidationRunRequestPayload,
  ConsolidationRunStatementsResponse,
  ConsolidationSummaryResponse,
} from "@/types/consolidation"

export interface OrgSetupSummaryForConsolidation {
  group: {
    id: string
    group_name: string
    reporting_currency: string
  } | null
  entities: Array<{
    id: string
    legal_name: string
    cp_entity_id: string | null
  }>
}

export interface ConsolidationTranslationEntityResult {
  org_entity_id: string
  entity_name: string
  functional_currency: string
  presentation_currency: string
  closing_rate: string
  average_rate: string
  translated_assets: string
  translated_liabilities: string
  translated_equity: string
  translated_net_profit: string
  cta_amount: string
}

export interface ConsolidationTranslationResponse {
  run_id: string | null
  org_group_id: string
  group_name: string
  presentation_currency: string
  as_of_date: string
  cta_account_code: string
  entity_results: ConsolidationTranslationEntityResult[]
  totals: {
    translated_assets: string
    translated_liabilities: string
    translated_equity: string
    translated_net_profit: string
    total_cta: string
  }
}

export const getOrgSetupSummaryForConsolidation =
  async (): Promise<OrgSetupSummaryForConsolidation> => {
    const response = await apiClient.get<OrgSetupSummaryForConsolidation>(
      "/api/v1/org-setup/summary",
    )
    return response.data
  }

export const getConsolidationSummary = async ({
  orgGroupId,
  asOfDate,
  fromDate,
  toDate,
}: {
  orgGroupId: string
  asOfDate: string
  fromDate?: string
  toDate?: string
}): Promise<ConsolidationSummaryResponse> => {
  const params = new URLSearchParams({
    org_group_id: orgGroupId,
    as_of_date: asOfDate,
  })
  if (fromDate) {
    params.set("from_date", fromDate)
  }
  if (toDate) {
    params.set("to_date", toDate)
  }
  const response = await apiClient.get<ConsolidationSummaryResponse>(
    `/api/v1/consolidation/summary?${params.toString()}`,
  )
  return response.data
}

export const runConsolidation = async (
  payload: ConsolidationRunRequestPayload,
): Promise<ConsolidationRunAcceptedResponse> => {
  const response = await apiClient.post<ConsolidationRunAcceptedResponse>(
    "/api/v1/consolidation/run",
    payload,
  )
  return response.data
}

export const getConsolidationRun = async (
  runId: string,
): Promise<ConsolidationRunDetailsResponse> => {
  const response = await apiClient.get<ConsolidationRunDetailsResponse>(
    `/api/v1/consolidation/runs/${runId}`,
  )
  return response.data
}

export const getConsolidationRunStatements = async (
  runId: string,
): Promise<ConsolidationRunStatementsResponse> => {
  const response = await apiClient.get<ConsolidationRunStatementsResponse>(
    `/api/v1/consolidation/runs/${runId}/statements`,
  )
  return response.data
}

export const getConsolidationTranslation = async (params: {
  orgGroupId: string
  presentationCurrency: string
  asOfDate: string
}): Promise<ConsolidationTranslationResponse> => {
  const query = new URLSearchParams({
    org_group_id: params.orgGroupId,
    presentation_currency: params.presentationCurrency,
    as_of_date: params.asOfDate,
  })
  const response = await apiClient.get<ConsolidationTranslationResponse>(
    `/api/v1/consolidation/translate?${query.toString()}`,
  )
  return response.data
}
