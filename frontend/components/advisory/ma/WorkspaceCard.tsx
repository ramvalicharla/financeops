"use client"

import Link from "next/link"
import type { MAWorkspace } from "@/lib/types/ma"
import { decimalStringToNumber } from "@/lib/utils"

interface WorkspaceCardProps {
  workspace: MAWorkspace
  ddCompletionPct?: string
  memberCount?: number
}

export function WorkspaceCard({ workspace, ddCompletionPct = "0.00", memberCount = 0 }: WorkspaceCardProps) {
  const completion = decimalStringToNumber(ddCompletionPct)

  return (
    <article className="rounded-xl border border-border bg-card p-4">
      <div className="flex items-start justify-between gap-3">
        <div>
          <h3 className="text-base font-semibold text-foreground">{workspace.deal_codename}</h3>
          <p className="text-xs text-muted-foreground">{workspace.target_company_name}</p>
        </div>
        <span className="rounded-full border border-border px-2 py-0.5 text-xs text-muted-foreground">
          {workspace.deal_status}
        </span>
      </div>
      <div className="mt-3 grid grid-cols-2 gap-2 text-xs">
        <p className="text-muted-foreground">Type</p>
        <p className="text-foreground">{workspace.deal_type}</p>
        <p className="text-muted-foreground">Members</p>
        <p className="text-foreground">{memberCount}</p>
      </div>
      <div className="mt-3">
        <div className="h-2 w-full rounded-full bg-background">
          <div className="h-2 rounded-full bg-[hsl(var(--brand-primary))]" style={{ width: `${Math.max(0, Math.min(100, completion))}%` }} />
        </div>
        <p className="mt-1 text-xs text-muted-foreground">DD completion: {ddCompletionPct}%</p>
      </div>
      <div className="mt-4 flex items-center gap-3">
        <Link href={`/advisory/ma/${workspace.id}`} className="text-sm text-[hsl(var(--brand-primary))]">
          Open Workspace
        </Link>
        <Link href={`/advisory/ma/${workspace.id}/valuation`} className="text-sm text-muted-foreground">
          Valuation
        </Link>
      </div>
    </article>
  )
}
