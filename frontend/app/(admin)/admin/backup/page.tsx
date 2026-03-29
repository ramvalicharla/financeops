"use client"

import { useEffect, useState } from "react"
import { getBackupStatus, listBackupRuns, verifyBackupIntegrity } from "@/lib/api/backup"
import type { BackupRun, BackupStatus } from "@/lib/types/backup"
import { BackupStatusCard } from "@/components/backup/BackupStatusCard"
import { BackupRunTable } from "@/components/backup/BackupRunTable"

const RUNBOOK_TEXT = `RTO: 4 hours | RPO: 1 hour\n\nRestore Procedure:\n1. Stop API workers\n2. RESTORE_CONFIRM=yes ./restore_postgres.sh <filename>\n3. ./verify_restore.sh\n4. alembic upgrade head\n5. Restart workers\n6. Monitor /health for 30 minutes`

export default function AdminBackupPage() {
  const [status, setStatus] = useState<BackupStatus | null>(null)
  const [runs, setRuns] = useState<BackupRun[]>([])
  const [integrity, setIntegrity] = useState<{ passed: boolean; checks: Record<string, boolean> } | null>(null)

  const load = async () => {
    const [statusData, runsData] = await Promise.all([
      getBackupStatus(),
      listBackupRuns({ limit: 10, offset: 0 }),
    ])
    setStatus(statusData)
    setRuns(runsData.data)
  }

  useEffect(() => {
    void load()
  }, [])

  const verify = async () => {
    const result = await verifyBackupIntegrity()
    setIntegrity(result)
    await load()
  }

  return (
    <div className="space-y-6">
      <header className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold text-foreground">Backup & DR</h1>
          <p className="text-sm text-muted-foreground">Recent backup runs and integrity verification.</p>
        </div>
        <button type="button" onClick={() => void verify()} className="rounded-md border border-border px-3 py-2 text-sm text-foreground">
          Verify Database Integrity
        </button>
      </header>

      {status ? <BackupStatusCard status={status} /> : null}
      <BackupRunTable runs={runs} />

      <section className="rounded-xl border border-border bg-card p-4">
        <h3 className="mb-2 text-lg font-semibold text-foreground">Runbook</h3>
        <pre className="whitespace-pre-wrap text-xs text-muted-foreground">{RUNBOOK_TEXT}</pre>
      </section>

      {integrity ? (
        <section className="rounded-xl border border-border bg-card p-4">
          <h3 className="mb-2 text-lg font-semibold text-foreground">Integrity Results</h3>
          <p className="text-sm text-foreground">Passed: {integrity.passed ? "Yes" : "No"}</p>
          <ul className="mt-2 space-y-1 text-sm text-muted-foreground">
            {Object.entries(integrity.checks).map(([name, ok]) => (
              <li key={name}>
                {name}: {ok ? "green" : "red"}
              </li>
            ))}
          </ul>
        </section>
      ) : null}
    </div>
  )
}

