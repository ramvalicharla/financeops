import apiClient from "@/lib/api/client"

export interface UserPreferencesPayload {
  sidebar_collapsed: boolean | null
}

export const getUserPreferences = async (): Promise<UserPreferencesPayload> => {
  const response = await apiClient.get<UserPreferencesPayload>("/api/v1/users/me/preferences")
  return response.data
}

export const updateUserPreferences = async (
  payload: Partial<UserPreferencesPayload>,
): Promise<UserPreferencesPayload> => {
  const response = await apiClient.patch<UserPreferencesPayload>(
    "/api/v1/users/me/preferences",
    payload,
  )
  return response.data
}
