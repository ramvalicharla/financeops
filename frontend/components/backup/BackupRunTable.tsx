import type { BackupRun } from "@/lib/types/backup"

interface BackupRunTableProps {
  runs: BackupRun[]
}

const formatBytes = (value: number | null): string => {
  if (value === null || value <= 0) {
    return "-"
  }
  const gb = value / (1024 * 1024 * 1024)
  if (gb >= 1) {
    return `${gb.toFixed(2)} GB`
  }
  const mb = value / (1024 * 1024)
  return `${mb.toFixed(2)} MB`
}

export function BackupRunTable({ runs }: BackupRunTableProps) {
  return (
    <div className="overflow-x-auto rounded-xl border border-border bg-card">
      <table aria-label="Backup runs" className="min-w-full text-sm">
        <thead className="border-b border-border text-left text-xs uppercase tracking-[0.14em] text-muted-foreground">
          <tr>
            <th scope="col" className="px-3 py-2">Type</th>
            <th scope="col" className="px-3 py-2">Status</th>
            <th scope="col" className="px-3 py-2">Started</th>
            <th scope="col" className="px-3 py-2">Duration</th>
            <th scope="col" className="px-3 py-2">Size</th>
            <th scope="col" className="px-3 py-2">Location</th>
            <th scope="col" className="px-3 py-2">Verified</th>
          </tr>
        </thead>
        <tbody>
          {runs.map((run) => {
            const duration = run.completed_at
              ? Math.max(
                  0,
                  Math.round((new Date(run.completed_at).getTime() - new Date(run.started_at).getTime()) / 1000),
                )
              : null
            return (
              <tr key={run.id} className="border-b border-border/50">
                <td className="px-3 py-2">{run.backup_type}</td>
                <td className="px-3 py-2">
                  <span
                    className={
                      run.status === "completed" || run.status === "verified"
                        ? "text-[hsl(var(--brand-success))]"
                        : run.status === "failed"
                          ? "text-[hsl(var(--brand-danger))]"
                          : "text-[hsl(var(--brand-primary))]"
                    }
                  >
                    {run.status}
                  </span>
                </td>
                <td className="px-3 py-2">{run.started_at}</td>
                <td className="px-3 py-2">{duration !== null ? `${duration}s` : "-"}</td>
                <td className="px-3 py-2">{formatBytes(run.size_bytes)}</td>
                <td className="px-3 py-2">{run.backup_location ?? "-"}</td>
                <td className="px-3 py-2">{run.verification_passed === null ? "-" : run.verification_passed ? "Yes" : "No"}</td>
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}

