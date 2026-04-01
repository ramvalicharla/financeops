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
