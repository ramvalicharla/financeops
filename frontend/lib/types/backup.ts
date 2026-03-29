export type BackupRun = {
  id: string
  backup_type: string
  status: string
  started_at: string
  completed_at: string | null
  size_bytes: number | null
  backup_location: string | null
  verification_passed: boolean | null
  error_message: string | null
  triggered_by: string
  retention_days: number
  created_at: string
}

export type BackupStatus = {
  last_full_backup: string | null
  last_full_backup_age_hours: string | null
  last_verified_restore: string | null
  is_backup_overdue: boolean
  recent_runs: BackupRun[]
  rag_status: "green" | "amber" | "red"
}
