import apiClient from "@/lib/api/client"
import type {
  ConsolidationEntity,
  ConsolidationSummary,
} from "@/types/consolidation"

export const getConsolidationEntities = async (
  tenantId?: string,
): Promise<ConsolidationEntity[]> => {
  const suffix = tenantId
    ? `?tenant_id=${encodeURIComponent(tenantId)}`
    : ""
  const response = await apiClient.get<ConsolidationEntity[]>(
    `/api/v1/consolidation/entities${suffix}`,
  )
  return response.data
}

export const getConsolidationSummary = async (
  entityIds: string[],
  period: string,
): Promise<ConsolidationSummary> => {
  const response = await apiClient.post<ConsolidationSummary>(
    "/api/v1/consolidation/summary",
    {
      entity_ids: entityIds,
      period,
    },
  )
  return response.data
}

export const getFXRates = async (
  period: string,
): Promise<Array<{ currency: string; rate_to_inr: string }>> => {
  const response = await apiClient.get<
    Array<{ currency: string; rate_to_inr: string }>
  >(`/api/v1/consolidation/fx-rates?period=${encodeURIComponent(period)}`)
  return response.data
}
