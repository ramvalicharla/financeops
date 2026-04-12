"use client"

import Link from "next/link"
import { Button } from "@/components/ui/button"
import { StateBadge } from "@/components/ui"
import { cn } from "@/lib/utils"

interface PeriodLockOverlayProps {
  periodLabel: string
  checklistHref: string
  status: string
  lockedAt?: string | null
  lockedBy?: string | null
  reason?: string | null
  readinessPass?: boolean
  blockers?: string[]
  warnings?: string[]
  checklistProgress?: {
    completed: number
    total: number
    status: string
    closedAt?: string | null
    closedByKnown?: boolean
  }
  canLock: boolean
  canUnlock: boolean
  isLocking?: boolean
  isUnlocking?: boolean
  onSoftClose: () => void
  onHardClose: () => void
  onUnlock: () => void
}

const ProgressBar = ({ value }: { value: number }) => (
  <div className="h-2 overflow-hidden rounded-full bg-muted">
    <div
      className="h-full rounded-full bg-[hsl(var(--brand-primary))] transition-all"
      style={{ width: `${Math.min(Math.max(value, 0), 100)}%` }}
    />
  </div>
)

export function PeriodLockOverlay({
  periodLabel,
  checklistHref,
  status,
  lockedAt,
  lockedBy,
  reason,
  readinessPass,
  blockers = [],
  warnings = [],
  checklistProgress,
  canLock,
  canUnlock,
  isLocking,
  isUnlocking,
  onSoftClose,
  onHardClose,
  onUnlock,
}: PeriodLockOverlayProps) {
  const lockedByLabel = lockedBy ?? "Not exposed by backend"
  const readinessTone = readinessPass ? "text-[hsl(var(--brand-success))]" : "text-[hsl(var(--brand-warning))]"
  const checklistPercent =
    checklistProgress && checklistProgress.total > 0
      ? Math.round((checklistProgress.completed / checklistProgress.total) * 100)
      : 0

  return (
    <section className="rounded-3xl border border-border bg-card p-5 shadow-sm">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <p className="text-xs uppercase tracking-wide text-muted-foreground">Period Lock Overlay</p>
          <h2 className="mt-1 text-xl font-semibold text-foreground">{periodLabel}</h2>
          <p className="mt-1 text-sm text-muted-foreground">
            Lock state is governed by the legacy close endpoint. Month-end checklist state is shown below.
          </p>
        </div>
        <StateBadge status={status} label={status} />
      </div>

      <div className="mt-5 grid gap-4 lg:grid-cols-3">
        <div className="rounded-2xl border border-border bg-background p-4">
          <p className="text-xs uppercase tracking-wide text-muted-foreground">Lock metadata</p>
          <div className="mt-3 space-y-2 text-sm">
            <p className="text-foreground">
              Locked at: <span className="text-muted-foreground">{lockedAt ?? "Unavailable"}</span>
            </p>
            <p className="text-foreground">
              Locked by: <span className="text-muted-foreground">{lockedByLabel}</span>
            </p>
            <p className="text-foreground">
              Reason: <span className="text-muted-foreground">{reason ?? "No reason recorded"}</span>
            </p>
          </div>
        </div>

        <div className="rounded-2xl border border-border bg-background p-4">
          <p className="text-xs uppercase tracking-wide text-muted-foreground">Readiness</p>
          <p className={cn("mt-2 text-sm font-semibold", readinessTone)}>
            {readinessPass ? "PASS" : "FAIL"}
          </p>
          <p className="mt-1 text-sm text-muted-foreground">
            {readinessPass
              ? "No blocking readiness issues were returned."
              : `${blockers.length} blocker(s) and ${warnings.length} warning(s) returned by the backend.`}
          </p>
        </div>

        <div className="rounded-2xl border border-border bg-background p-4">
          <p className="text-xs uppercase tracking-wide text-muted-foreground">Month-end checklist</p>
          {checklistProgress ? (
            <div className="mt-3 space-y-2">
              <p className="text-sm text-foreground">
                {checklistProgress.completed} of {checklistProgress.total} tasks complete
              </p>
              <ProgressBar value={checklistPercent} />
              <p className="text-xs text-muted-foreground">
                Status: {checklistProgress.status}
                {checklistProgress.closedAt ? ` - Closed at ${checklistProgress.closedAt}` : ""}
              </p>
              {!checklistProgress.closedByKnown ? (
                <p className="text-xs text-muted-foreground">
                  Closed-by attribution is not exposed by the current API.
                </p>
              ) : null}
            </div>
          ) : (
            <p className="mt-3 text-sm text-muted-foreground">No month-end checklist record is loaded.</p>
          )}
        </div>
      </div>

      {(blockers.length > 0 || warnings.length > 0) ? (
        <div className="mt-4 grid gap-4 md:grid-cols-2">
          <div className="rounded-2xl border border-[hsl(var(--brand-danger)/0.22)] bg-[hsl(var(--brand-danger)/0.06)] p-4">
            <p className="text-sm font-semibold text-foreground">Blockers</p>
            {blockers.length ? (
              <ul className="mt-2 list-disc space-y-1 pl-5 text-sm text-foreground">
                {blockers.map((item) => (
                  <li key={item}>{item}</li>
                ))}
              </ul>
            ) : (
              <p className="mt-2 text-sm text-muted-foreground">No blockers.</p>
            )}
          </div>
          <div className="rounded-2xl border border-[hsl(var(--brand-warning)/0.22)] bg-[hsl(var(--brand-warning)/0.06)] p-4">
            <p className="text-sm font-semibold text-foreground">Warnings</p>
            {warnings.length ? (
              <ul className="mt-2 list-disc space-y-1 pl-5 text-sm text-foreground">
                {warnings.map((item) => (
                  <li key={item}>{item}</li>
                ))}
              </ul>
            ) : (
              <p className="mt-2 text-sm text-muted-foreground">No warnings.</p>
            )}
          </div>
        </div>
      ) : null}

      <div className="mt-5 flex flex-wrap items-center gap-3">
        <Button type="button" variant="outline" onClick={onSoftClose} disabled={!canLock || isLocking}>
          Soft Close
        </Button>
        <Button type="button" variant="outline" onClick={onHardClose} disabled={!canLock || isLocking}>
          Hard Close
        </Button>
        <Button type="button" variant="outline" onClick={onUnlock} disabled={!canUnlock || isUnlocking}>
          Unlock
        </Button>
        <Button type="button" variant="ghost" asChild>
          <Link href={checklistHref}>Open Checklist</Link>
        </Button>
      </div>
    </section>
  )
}
