import apiClient, { parseWithSchema } from "@/lib/api/client"
import { MISDashboardSchema } from "@/lib/schemas/mis"
import type { MISDashboard, MISPeriod } from "@/types/mis"

export const getMISDashboard = async (
  entityId: string,
  period: string,
): Promise<MISDashboard> => {
  const endpoint = `/api/v1/mis/dashboard?entity_id=${encodeURIComponent(entityId)}&period=${encodeURIComponent(period)}`
  const response = await apiClient.get<unknown>(
    endpoint,
  )
  return parseWithSchema(
    endpoint,
    response.data,
    MISDashboardSchema,
  ) as MISDashboard
}

export const getMISPeriods = async (entityId: string): Promise<MISPeriod[]> => {
  const response = await apiClient.get<MISPeriod[]>(
    `/api/v1/mis/periods?entity_id=${encodeURIComponent(entityId)}`,
  )
  return response.data
}
