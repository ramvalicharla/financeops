export type ModuleHealthStatus = "healthy" | "degraded" | "unhealthy" | "unknown"

export type ServiceRegistryModule = {
  id: string
  module_name: string
  module_version: string
  description: string | null
  is_enabled: boolean
  health_status: ModuleHealthStatus
  last_health_check: string | null
  route_prefix: string | null
  depends_on: string[]
  created_at: string
  updated_at: string
}

export type ServiceRegistryTaskStatus = "success" | "failure" | "timeout" | null

export type ServiceRegistryTask = {
  id: string
  task_name: string
  module_name: string
  queue_name: string
  description: string | null
  avg_duration_seconds: string | null
  success_rate_7d: string | null
  last_run_at: string | null
  last_run_status: ServiceRegistryTaskStatus
  is_scheduled: boolean
  schedule_cron: string | null
  created_at: string
  updated_at: string
}

export type ServiceDashboard = {
  overall_status: "healthy" | "degraded" | "unhealthy"
  modules: ServiceRegistryModule[]
  tasks: ServiceRegistryTask[]
  queue_depths: Record<string, number>
  unhealthy_modules: ServiceRegistryModule[]
}

export type PaginatedResponse<T> = {
  data: T[]
  total: number
  limit: number
  offset: number
}

