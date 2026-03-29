import apiClient from "@/lib/api/client"
import type { BackupRun, BackupStatus } from "@/lib/types/backup"

export type PaginatedResponse<T> = {
  data: T[]
  total: number
  limit: number
  offset: number
}

export const getBackupStatus = async (): Promise<BackupStatus> => {
  const response = await apiClient.get<BackupStatus>("/api/v1/backup/status")
  return response.data
}

export const listBackupRuns = async (params?: {
  limit?: number
  offset?: number
}): Promise<PaginatedResponse<BackupRun>> => {
  const search = new URLSearchParams()
  search.set("limit", String(params?.limit ?? 10))
  search.set("offset", String(params?.offset ?? 0))
  const response = await apiClient.get<PaginatedResponse<BackupRun>>(
    `/api/v1/backup/runs?${search.toString()}`,
  )
  return response.data
}

export const verifyBackupIntegrity = async (): Promise<{ passed: boolean; checks: Record<string, boolean> }> => {
  const response = await apiClient.post<{ passed: boolean; checks: Record<string, boolean> }>(
    "/api/v1/backup/verify-integrity",
  )
  return response.data
}

export const logBackupRun = async (payload: {
  backup_type: string
  status: string
  triggered_by: string
  size_bytes?: number
  backup_location?: string
  verification_passed?: boolean
  error_message?: string
  retention_days?: number
}): Promise<BackupRun> => {
  const response = await apiClient.post<BackupRun>("/api/v1/backup/log", payload)
  return response.data
}

