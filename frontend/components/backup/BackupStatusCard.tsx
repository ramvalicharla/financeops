import type { BackupStatus } from "@/lib/types/backup"
import { RAGBadge } from "@/components/compliance/RAGBadge"

interface BackupStatusCardProps {
  status: BackupStatus
}

export function BackupStatusCard({ status }: BackupStatusCardProps) {
  return (
    <section className="rounded-xl border border-border bg-card p-4">
      <div className="mb-3 flex items-center justify-between">
        <h3 className="text-lg font-semibold text-foreground">Backup Status</h3>
        <RAGBadge status={status.rag_status} />
      </div>
      <div className="grid gap-2 text-sm text-muted-foreground md:grid-cols-2">
        <p>Last full backup: {status.last_full_backup ?? "Never"}</p>
        <p>Backup age hours: {status.last_full_backup_age_hours ?? "-"}</p>
        <p>Last verified restore: {status.last_verified_restore ?? "Never"}</p>
        <p className={status.is_backup_overdue ? "text-[hsl(var(--brand-danger))]" : "text-muted-foreground"}>
          Overdue: {status.is_backup_overdue ? "Yes" : "No"}
        </p>
      </div>
    </section>
  )
}

