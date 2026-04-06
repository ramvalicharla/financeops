"use client"

import Link from "next/link"
import { Button } from "@/components/ui/button"
import { type AuditorPortalAccess } from "@/lib/types/sprint11"

export type AuditorAccessPanelProps = {
  access: AuditorPortalAccess
  plainToken?: string
  completionPct?: string
  canRevoke?: boolean
  revokeTitle?: string
  onRevoke: () => Promise<void>
}

export function AuditorAccessPanel({
  access,
  plainToken,
  completionPct,
  canRevoke = true,
  revokeTitle,
  onRevoke,
}: AuditorAccessPanelProps) {
  return (
    <div className="rounded-xl border border-border bg-card p-4">
      <p className="text-sm font-semibold text-foreground">{access.auditor_email}</p>
      <p className="text-xs text-muted-foreground">{access.auditor_firm}</p>
      <p className="mt-1 text-xs text-muted-foreground">{access.engagement_name}</p>
      <p className="mt-2 text-xs text-muted-foreground">
        Valid: {access.valid_from} to {access.valid_until}
      </p>
      <p className="mt-1 text-xs text-muted-foreground">
        Last accessed: {access.last_accessed_at ?? "Never"}
      </p>
      {completionPct ? (
        <p className="mt-1 text-xs text-muted-foreground">Completion: {completionPct}%</p>
      ) : null}
      {plainToken ? (
        <div className="mt-3 rounded-md border border-amber-500/30 bg-gray-900 p-3">
          <div className="font-mono text-xs text-white">{plainToken}</div>
          <p className="mt-2 text-[11px] text-amber-400">
            Copy this token now. It will never be shown again.
          </p>
        </div>
      ) : null}
      <div className="mt-3 flex flex-wrap gap-2">
        <Link
          href={`/audit/${access.id}`}
          className="rounded-md border border-border px-3 py-1.5 text-xs text-foreground"
        >
          View PBC Tracker
        </Link>
        <Button
          variant="outline"
          size="sm"
          onClick={() => void onRevoke()}
          disabled={!canRevoke}
          title={!canRevoke ? revokeTitle : undefined}
        >
          Revoke Access
        </Button>
      </div>
    </div>
  )
}
