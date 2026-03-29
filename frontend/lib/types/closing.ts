export interface ChecklistRunSummary {
  id: string
  period: string
  status: "open" | "in_progress" | "completed" | "locked"
  progress_pct: string
  target_close_date: string | null
  actual_close_date: string | null
  days_until_period_end: number
  is_overdue: boolean
  completed_count: number
  total_count: number
}

export interface ChecklistTaskItem {
  id: string
  run_id: string
  template_task_id: string
  task_name: string
  assigned_to: string | null
  assigned_role: string | null
  due_date: string | null
  status: "not_started" | "in_progress" | "completed" | "blocked" | "skipped"
  completed_at: string | null
  completed_by: string | null
  notes: string | null
  is_auto_completed: boolean
  auto_completed_by_event: string | null
  order_index: number
  dependency_met: boolean
  depends_on_task_ids: string[]
}

export interface ChecklistPeriodPayload {
  run: ChecklistRunSummary
  tasks: ChecklistTaskItem[]
}

export interface ClosingAnalytics {
  avg_days_to_close: string
  fastest_close_period: string | null
  slowest_close_period: string | null
  on_time_rate: string
  most_blocked_task: string | null
  trend: "improving" | "stable" | "worsening"
}
