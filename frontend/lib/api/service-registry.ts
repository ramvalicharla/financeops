import apiClient from "@/lib/api/client"
import type {
  PaginatedResponse,
  ServiceDashboard,
  ServiceRegistryModule,
  ServiceRegistryTask,
} from "@/lib/types/service-registry"

export const getServiceDashboard = async (): Promise<ServiceDashboard> => {
  const response = await apiClient.get<ServiceDashboard>("/api/v1/platform/services/dashboard")
  return response.data
}

export const runServiceHealthCheck = async (): Promise<{
  total: number
  healthy: number
  degraded: number
  unhealthy: number
  unknown: number
  modules: ServiceRegistryModule[]
}> => {
  const response = await apiClient.post<{
    total: number
    healthy: number
    degraded: number
    unhealthy: number
    unknown: number
    modules: ServiceRegistryModule[]
  }>("/api/v1/platform/services/health-check")
  return response.data
}

export const listServiceModules = async (params?: {
  limit?: number
  offset?: number
}): Promise<PaginatedResponse<ServiceRegistryModule>> => {
  const search = new URLSearchParams()
  search.set("limit", String(params?.limit ?? 200))
  search.set("offset", String(params?.offset ?? 0))
  const response = await apiClient.get<PaginatedResponse<ServiceRegistryModule>>(
    `/api/v1/platform/services/modules?${search.toString()}`,
  )
  return response.data
}

export const listServiceTasks = async (params?: {
  queue_name?: string
  is_scheduled?: boolean
  limit?: number
  offset?: number
}): Promise<PaginatedResponse<ServiceRegistryTask>> => {
  const search = new URLSearchParams()
  if (params?.queue_name) search.set("queue_name", params.queue_name)
  if (params?.is_scheduled !== undefined) search.set("is_scheduled", String(params.is_scheduled))
  search.set("limit", String(params?.limit ?? 200))
  search.set("offset", String(params?.offset ?? 0))
  const response = await apiClient.get<PaginatedResponse<ServiceRegistryTask>>(
    `/api/v1/platform/services/tasks?${search.toString()}`,
  )
  return response.data
}

export const toggleServiceModule = async (
  moduleName: string,
  isEnabled: boolean,
): Promise<ServiceRegistryModule> => {
  const response = await apiClient.patch<ServiceRegistryModule>(
    `/api/v1/platform/services/modules/${moduleName}/toggle`,
    { is_enabled: isEnabled },
  )
  return response.data
}

