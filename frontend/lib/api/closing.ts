import apiClient from "@/lib/api/client"
import type { ChecklistPeriodPayload, ClosingAnalytics } from "@/lib/types/closing"

export const fetchChecklistForPeriod = async (
  period: string,
): Promise<ChecklistPeriodPayload> => {
  const response = await apiClient.get<ChecklistPeriodPayload>(`/api/v1/close/${period}`)
  return response.data
}

export const patchChecklistTaskStatus = async (
  period: string,
  taskId: string,
  status: string,
  notes?: string,
): Promise<{
  task: { id: string; status: string; notes: string | null; completed_at: string | null }
  run: { id: string; status: string; progress_pct: string }
}> => {
  const response = await apiClient.patch(`/api/v1/close/${period}/tasks/${taskId}`, {
    status,
    notes: notes ?? null,
  })
  return response.data
}

export const assignChecklistTask = async (
  period: string,
  taskId: string,
  userId: string,
): Promise<{ task_id: string; assigned_to: string }> => {
  const response = await apiClient.post(`/api/v1/close/${period}/tasks/${taskId}/assign`, {
    user_id: userId,
  })
  return response.data
}

export const fetchClosingAnalytics = async (): Promise<ClosingAnalytics> => {
  const response = await apiClient.get<ClosingAnalytics>("/api/v1/close/analytics")
  return response.data
}
