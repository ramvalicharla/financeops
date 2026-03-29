"use client"

import { cn } from "@/lib/utils"
import type { SyncRunStatus } from "@/types/sync"

interface SyncStatusBadgeProps {
  status: SyncRunStatus
}

const statusStyles: Record<SyncRunStatus, string> = {
  COMPLETED: "bg-[hsl(var(--brand-success)/0.2)] text-[hsl(var(--brand-success))]",
  RUNNING: "bg-[hsl(var(--brand-primary)/0.2)] text-[hsl(var(--brand-primary))]",
  HALTED: "bg-[hsl(var(--brand-danger)/0.2)] text-[hsl(var(--brand-danger))]",
  PAUSED: "bg-[hsl(var(--brand-warning)/0.2)] text-[hsl(var(--brand-warning))]",
  DUPLICATE_SYNC: "bg-muted text-muted-foreground",
  PENDING: "bg-muted text-muted-foreground",
  CANCELLED: "bg-muted text-muted-foreground",
}

export function SyncStatusBadge({ status }: SyncStatusBadgeProps) {
  const isPulsing = status === "RUNNING" || status === "PENDING"
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 rounded-full px-2 py-1 text-xs font-medium",
        statusStyles[status],
      )}
    >
      {isPulsing ? <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-current" /> : null}
      {status.replaceAll("_", " ")}
    </span>
  )
}
