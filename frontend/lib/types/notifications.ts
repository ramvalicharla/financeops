export type NotificationType =
  | "anomaly_detected"
  | "anomaly_escalated"
  | "close_deadline_approaching"
  | "close_overdue"
  | "task_assigned"
  | "task_completed"
  | "task_blocked"
  | "approval_required"
  | "approval_completed"
  | "approval_rejected"
  | "budget_variance_alert"
  | "budget_approved"
  | "expense_approved"
  | "expense_rejected"
  | "report_ready"
  | "board_pack_ready"
  | "erp_sync_complete"
  | "erp_sync_failed"
  | "fdd_complete"
  | "ppa_complete"
  | "marketplace_template_approved"
  | "marketplace_payout_processed"
  | "partner_commission_earned"
  | "system_alert"

export type NotificationReadState = {
  is_read: boolean
  read_at: string | null
  is_dismissed: boolean
  dismissed_at: string | null
  updated_at: string
}

export type NotificationRow = {
  id: string
  notification_type: NotificationType
  title: string
  body: string
  action_url: string | null
  metadata: Record<string, unknown>
  channels_sent: string[]
  created_at: string
  read_state: NotificationReadState
}

export type NotificationListResponse = {
  unread_count: number
  notifications: NotificationRow[]
  total: number
  limit: number
  offset: number
}

export type NotificationPreferences = {
  id: string
  tenant_id: string
  user_id: string
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
  created_at: string
  updated_at: string
}

