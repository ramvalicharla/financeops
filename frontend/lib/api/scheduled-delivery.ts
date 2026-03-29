import apiClient from "@/lib/api/client"
import type {
  CreateDeliveryScheduleRequest,
  DeliveryLogResponse,
  DeliveryScheduleResponse,
  TriggerDeliveryResponse,
  UpdateDeliveryScheduleRequest,
} from "@/lib/types/scheduled-delivery"

export const createDeliverySchedule = async (
  body: CreateDeliveryScheduleRequest,
): Promise<DeliveryScheduleResponse> => {
  const response = await apiClient.post<DeliveryScheduleResponse>(
    "/api/v1/delivery/schedules",
    body,
  )
  return response.data
}

export const fetchDeliverySchedules = async (params?: {
  active_only?: boolean
}): Promise<DeliveryScheduleResponse[]> => {
  const search = new URLSearchParams()
  if (params?.active_only !== undefined) {
    search.set("active_only", params.active_only ? "true" : "false")
  }
  const query = search.toString()
  const response = await apiClient.get<
    DeliveryScheduleResponse[] | { data: DeliveryScheduleResponse[] }
  >(
    `/api/v1/delivery/schedules${query ? `?${query}` : ""}`,
  )
  return Array.isArray(response.data) ? response.data : response.data.data
}

export const fetchDeliverySchedule = async (
  id: string,
): Promise<DeliveryScheduleResponse> => {
  const response = await apiClient.get<DeliveryScheduleResponse>(
    `/api/v1/delivery/schedules/${id}`,
  )
  return response.data
}

export const updateDeliverySchedule = async (
  id: string,
  body: UpdateDeliveryScheduleRequest,
): Promise<DeliveryScheduleResponse> => {
  const response = await apiClient.patch<DeliveryScheduleResponse>(
    `/api/v1/delivery/schedules/${id}`,
    body,
  )
  return response.data
}

export const deleteDeliverySchedule = async (id: string): Promise<void> => {
  await apiClient.delete(`/api/v1/delivery/schedules/${id}`)
}

export const triggerDeliverySchedule = async (
  id: string,
): Promise<TriggerDeliveryResponse> => {
  const response = await apiClient.post<TriggerDeliveryResponse>(
    `/api/v1/delivery/schedules/${id}/trigger`,
  )
  return response.data
}

export const fetchDeliveryLogs = async (params?: {
  schedule_id?: string
  status?: string
  limit?: number
}): Promise<DeliveryLogResponse[]> => {
  const search = new URLSearchParams()
  if (params?.schedule_id) {
    search.set("schedule_id", params.schedule_id)
  }
  if (params?.status) {
    search.set("status", params.status)
  }
  if (params?.limit !== undefined) {
    search.set("limit", String(params.limit))
  }
  const query = search.toString()
  const response = await apiClient.get<
    DeliveryLogResponse[] | { data: DeliveryLogResponse[] }
  >(
    `/api/v1/delivery/logs${query ? `?${query}` : ""}`,
  )
  return Array.isArray(response.data) ? response.data : response.data.data
}

export const fetchDeliveryLog = async (id: string): Promise<DeliveryLogResponse> => {
  const response = await apiClient.get<DeliveryLogResponse>(`/api/v1/delivery/logs/${id}`)
  return response.data
}
