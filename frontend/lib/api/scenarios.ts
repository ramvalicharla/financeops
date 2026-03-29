import apiClient from "@/lib/api/client"
import type {
  PaginatedResult,
  ScenarioComparisonPayload,
  ScenarioDefinition,
  ScenarioResultSummary,
  ScenarioSet,
} from "@/lib/types/scenario"

export const createScenarioSet = async (payload: {
  name: string
  base_period: string
  horizon_months: number
  base_forecast_run_id?: string
}): Promise<{ scenario_set: ScenarioSet; scenario_definitions: ScenarioDefinition[] }> => {
  const response = await apiClient.post<{
    scenario_set: ScenarioSet
    scenario_definitions: ScenarioDefinition[]
  }>("/api/v1/scenarios", payload)
  return response.data
}

export const listScenarioSets = async (params?: {
  limit?: number
  offset?: number
}): Promise<PaginatedResult<ScenarioSet>> => {
  const search = new URLSearchParams()
  if (params?.limit !== undefined) search.set("limit", String(params.limit))
  if (params?.offset !== undefined) search.set("offset", String(params.offset))
  const query = search.toString()
  const response = await apiClient.get<PaginatedResult<ScenarioSet>>(
    `/api/v1/scenarios${query ? `?${query}` : ""}`,
  )
  return response.data
}

export const getScenarioSet = async (
  setId: string,
): Promise<{
  scenario_set: ScenarioSet
  scenario_definitions: ScenarioDefinition[]
  latest_results: Array<{ id: string; scenario_definition_id: string; computed_at: string }>
}> => {
  const response = await apiClient.get<{
    scenario_set: ScenarioSet
    scenario_definitions: ScenarioDefinition[]
    latest_results: Array<{ id: string; scenario_definition_id: string; computed_at: string }>
  }>(`/api/v1/scenarios/${setId}`)
  return response.data
}

export const updateScenarioDefinition = async (
  setId: string,
  definitionId: string,
  payload: { driver_overrides: Record<string, string>; scenario_label?: string },
): Promise<ScenarioDefinition> => {
  const response = await apiClient.patch<ScenarioDefinition>(
    `/api/v1/scenarios/${setId}/scenarios/${definitionId}`,
    payload,
  )
  return response.data
}

export const computeScenarios = async (
  setId: string,
): Promise<{ results: ScenarioResultSummary[] }> => {
  const response = await apiClient.post<{ results: ScenarioResultSummary[] }>(
    `/api/v1/scenarios/${setId}/compute`,
  )
  return response.data
}

export const getScenarioComparison = async (setId: string): Promise<ScenarioComparisonPayload> => {
  const response = await apiClient.get<ScenarioComparisonPayload>(`/api/v1/scenarios/${setId}/comparison`)
  return response.data
}

export const exportScenarioSet = async (setId: string): Promise<Blob> => {
  const response = await apiClient.get(`/api/v1/scenarios/${setId}/export`, {
    responseType: "blob",
  })
  return response.data as Blob
}

