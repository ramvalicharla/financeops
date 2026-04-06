import apiClient from "@/lib/api/client"
import type { TenantProfile } from "@/types/api"

export const getCurrentTenantProfile = async (): Promise<TenantProfile> => {
  const response = await apiClient.get<TenantProfile>("/api/v1/tenants/me")
  return response.data
}
