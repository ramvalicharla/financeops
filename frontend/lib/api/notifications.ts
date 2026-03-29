import apiClient from "@/lib/api/client"
import type {
  NotificationListResponse,
  NotificationPreferences,
} from "@/lib/types/notifications"

export const listNotifications = async (params?: {
  is_read?: boolean
  type?: string
  limit?: number
  offset?: number
}): Promise<NotificationListResponse> => {
  const search = new URLSearchParams()
  if (params?.is_read !== undefined) {
    search.set("is_read", String(params.is_read))
  }
  if (params?.type) {
    search.set("type", params.type)
  }
  search.set("limit", String(params?.limit ?? 20))
  search.set("offset", String(params?.offset ?? 0))

  const response = await apiClient.get<NotificationListResponse>(
    `/api/v1/notifications?${search.toString()}`,
  )
  return response.data
}

export const markNotificationsRead = async (
  notificationIds: string[],
): Promise<{ updated: number }> => {
  const response = await apiClient.post<{ updated: number }>(
    "/api/v1/notifications/read",
    { notification_ids: notificationIds },
  )
  return response.data
}

export const markAllNotificationsRead = async (): Promise<{ updated: number }> => {
  const response = await apiClient.post<{ updated: number }>(
    "/api/v1/notifications/read-all",
  )
  return response.data
}

export const getUnreadNotificationCount = async (): Promise<number> => {
  const response = await apiClient.get<{ count: number }>(
    "/api/v1/notifications/unread-count",
  )
  return response.data.count
}

export const getNotificationPreferences = async (): Promise<NotificationPreferences> => {
  const response = await apiClient.get<NotificationPreferences>(
    "/api/v1/notifications/preferences",
  )
  return response.data
}

export const updateNotificationPreferences = async (
  updates: Partial<{
    email_enabled: boolean
    inapp_enabled: boolean
    push_enabled: boolean
    quiet_hours_start: string | null
    quiet_hours_end: string | null
    timezone: string
    type_preferences: Record<
      string,
      {
        email?: boolean
        inapp?: boolean
        push?: boolean
      }
    >
  }>,
): Promise<NotificationPreferences> => {
  const response = await apiClient.patch<NotificationPreferences>(
    "/api/v1/notifications/preferences",
    updates,
  )
  return response.data
}

