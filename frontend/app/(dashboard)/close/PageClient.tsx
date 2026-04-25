"use client"

import Link from "next/link"
import { useMemo, useState } from "react"
import { useSearchParams } from "next/navigation"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { useSession } from "next-auth/react"
import {
  closeMonthendChecklist,
  getMonthendChecklist,
  getMonthendChecklists,
  getPeriodStatus,
  lockPeriod,
  runReadiness,
  unlockPeriod,
  type MonthendChecklistTask,
} from "@/lib/api/close-governance"
import { useTenantStore } from "@/lib/store/tenant"
import { useWorkspaceStore } from "@/lib/store/workspace"
import {
  canPerformAction,
} from "@/lib/ui-access"
import { queryKeys } from "@/lib/query/keys"
import { Button } from "@/components/ui/button"
import { PeriodLockOverlay } from "./_components/PeriodLockOverlay"
import { LockReasonDialog } from "./_components/LockReasonDialog"
import { ChecklistCloseDialog } from "./_components/ChecklistCloseDialog"
import { ApprovalGraph } from "./_components/ApprovalGraph"

const toPeriodParts = (value: string): { fiscalYear: number; periodNumber: number } => {
  const [year, month] = value.split("-")
  const fiscalYear = Number.parseInt(year, 10)
  const periodNumber = Number.parseInt(month, 10)
  return {
    fiscalYear: Number.isFinite(fiscalYear) ? fiscalYear : new Date().getFullYear(),
    periodNumber: Number.isFinite(periodNumber) ? periodNumber : new Date().getMonth() + 1,
  }
}

type PendingDialogAction =
  | { action: "lock"; lockType: "SOFT_CLOSED" | "HARD_CLOSED" }
  | { action: "unlock" }
  | null

const normalize = (value: string): string => value.trim().toLowerCase().replace(/\s+/g, "_")

export default function ClosePage() {
  const searchParams = useSearchParams()
  const { data: session } = useSession()
  const userRole = String((session?.user as { role?: string } | undefined)?.role ?? "")
  const canLock = canPerformAction("close.lock", userRole)
  const canUnlock = canPerformAction("close.unlock", userRole)
  const queryClient = useQueryClient()
  const entityId = useWorkspaceStore((s) => s.entityId)
  const entityRoles = useTenantStore((state) => state.entity_roles)
  const initialPeriod = searchParams?.get("period") ?? new Date().toISOString().slice(0, 7)
  const [period, setPeriod] = useState(initialPeriod)
  const [pendingDialogAction, setPendingDialogAction] = useState<PendingDialogAction>(null)
  const [showCloseChecklistDialog, setShowCloseChecklistDialog] = useState(false)
  const { fiscalYear, periodNumber } = useMemo(() => toPeriodParts(period), [period])
  const activeEntity = useMemo(
    () => entityRoles.find((role) => role.entity_id === entityId) ?? null,
    [entityId, entityRoles],
  )

  const periodQuery = useQuery({
    queryKey: queryKeys.close.periodStatus(entityId, fiscalYear, periodNumber),
    queryFn: async () =>
      getPeriodStatus({
        org_entity_id: entityId ?? undefined,
        fiscal_year: fiscalYear,
        period_number: periodNumber,
      }),
    enabled: Boolean(entityId),
  })

  const readinessQuery = useQuery({
    queryKey: queryKeys.close.readiness(entityId, fiscalYear, periodNumber),
    queryFn: async () =>
      runReadiness({
        org_entity_id: entityId as string,
        fiscal_year: fiscalYear,
        period_number: periodNumber,
      }),
    enabled: Boolean(entityId),
  })

  const monthendListQuery = useQuery({
    queryKey: queryKeys.close.monthendList(activeEntity?.entity_name ?? null),
    queryFn: async () =>
      getMonthendChecklists({
        entity_name: activeEntity?.entity_name ?? undefined,
        limit: 24,
      }),
    enabled: Boolean(activeEntity?.entity_name),
  })

  const currentMonthendChecklist = useMemo(
    () =>
      monthendListQuery.data?.checklists.find(
        (checklist) =>
          checklist.period_year === fiscalYear && checklist.period_month === periodNumber,
      ) ?? null,
    [fiscalYear, monthendListQuery.data?.checklists, periodNumber],
  )

  const monthendDetailQuery = useQuery({
    queryKey: queryKeys.close.monthendDetail(currentMonthendChecklist?.checklist_id ?? null),
    queryFn: async () =>
      currentMonthendChecklist
        ? getMonthendChecklist(currentMonthendChecklist.checklist_id)
        : null,
    enabled: Boolean(currentMonthendChecklist?.checklist_id),
  })

  const refresh = async (): Promise<void> => {
    await queryClient.invalidateQueries({ queryKey: queryKeys.close.periodStatusAll() })
    await queryClient.invalidateQueries({ queryKey: queryKeys.close.readinessAll() })
    await queryClient.invalidateQueries({ queryKey: queryKeys.close.monthendListAll() })
    await queryClient.invalidateQueries({ queryKey: queryKeys.close.monthendDetailAll() })
  }

  const lockMutation = useMutation({
    mutationFn: ({
      lockType,
      reason,
    }: {
      lockType: "SOFT_CLOSED" | "HARD_CLOSED"
      reason: string
    }) => {
      return lockPeriod({
        org_entity_id: entityId ?? undefined,
        fiscal_year: fiscalYear,
        period_number: periodNumber,
        lock_type: lockType,
        reason,
      })
    },
    onSuccess: refresh,
  })

  const unlockMutation = useMutation({
    mutationFn: ({ reason }: { reason: string }) => {
      return unlockPeriod({
        org_entity_id: entityId ?? undefined,
        fiscal_year: fiscalYear,
        period_number: periodNumber,
        reason,
      })
    },
    onSuccess: refresh,
  })

  const closeChecklistMutation = useMutation({
    mutationFn: ({ notes }: { notes: string }) => {
      if (!currentMonthendChecklist) {
        throw new Error("No month-end checklist is loaded for the current period.")
      }
      return closeMonthendChecklist({
        checklistId: currentMonthendChecklist.checklist_id,
        notes,
      })
    },
    onSuccess: refresh,
  })

  const handleDialogConfirm = (reason: string) => {
    if (!pendingDialogAction) {
      return
    }

    const currentAction = pendingDialogAction
    setPendingDialogAction(null)

    if (currentAction.action === "lock") {
      lockMutation.mutate({ lockType: currentAction.lockType, reason })
      return
    }

    unlockMutation.mutate({ reason })
  }

  const checklistTasks: MonthendChecklistTask[] = monthendDetailQuery.data?.tasks ?? []
  const completedTasks = checklistTasks.filter((task) => normalize(task.status) === "completed").length
  const checklistProgress = checklistTasks.length
    ? Math.round((completedTasks / checklistTasks.length) * 100)
    : 0
  const monthendStatus = monthendDetailQuery.data?.status ?? currentMonthendChecklist?.status ?? "Unavailable"
  const monthendClosedAt = monthendDetailQuery.data?.closed_at ?? null

  const approvalStages = [
    {
      id: "readiness",
      label: "Readiness review",
      status: readinessQuery.data?.pass ? "completed" : "pending",
      detail: readinessQuery.data?.pass
        ? "Backend readiness checks passed."
        : "Backend readiness checks returned blockers.",
    },
    {
      id: "period-lock",
      label: "Period lock state",
      status: periodQuery.data?.status ?? "open",
      detail: periodQuery.data?.reason ?? "Current period state returned by the backend.",
      completedAt: periodQuery.data?.locked_at ?? null,
    },
    {
      id: "monthend",
      label: "Month-end checklist",
      status: monthendStatus,
      detail: currentMonthendChecklist
        ? `${completedTasks} of ${checklistTasks.length} month-end tasks complete.`
        : "No checklist loaded for the selected period.",
      completedAt: monthendClosedAt,
    },
  ]

  const readinessPass = readinessQuery.data?.pass ?? false
  const readinessBlockers = readinessQuery.data?.blockers ?? []
  const readinessWarnings = readinessQuery.data?.warnings ?? []

  return (
    <div className="space-y-6 p-6">
      <header className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold text-foreground">Period Close Control</h1>
          <p className="text-sm text-muted-foreground">
            Lock or unlock periods, review readiness, and inspect month-end checklist governance.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <input
            className="rounded-md border border-border bg-background px-3 py-2 text-sm"
            type="month"
            value={period}
            onChange={(event) => setPeriod(event.target.value)}
          />
          <Button variant="outline" asChild>
            <Link href={`/close/checklist?period=${period}`}>Open Checklist</Link>
          </Button>
        </div>
      </header>

      {!entityId ? (
        <section className="rounded-xl border border-border bg-card p-5">
          <p className="text-sm text-muted-foreground">Select an active entity to manage period close.</p>
        </section>
      ) : periodQuery.isLoading || readinessQuery.isLoading ? (
        <section className="rounded-xl border border-border bg-card p-5">
          <p className="text-sm text-muted-foreground">Loading period close governance...</p>
        </section>
      ) : periodQuery.error ? (
        <section className="rounded-xl border border-border bg-card p-5">
          <p className="text-sm text-[hsl(var(--brand-danger))]">Failed to load period status.</p>
        </section>
      ) : (
        <>
          <PeriodLockOverlay
            periodLabel={`${fiscalYear}-${String(periodNumber).padStart(2, "0")}`}
            checklistHref={`/close/checklist?period=${period}`}
            status={periodQuery.data?.status ?? "OPEN"}
            lockedAt={periodQuery.data?.locked_at}
            lockedBy={periodQuery.data?.locked_by}
            reason={periodQuery.data?.reason}
            readinessPass={readinessPass}
            blockers={readinessBlockers}
            warnings={readinessWarnings}
            checklistProgress={
              currentMonthendChecklist
                ? {
                    completed: completedTasks,
                    total: checklistTasks.length,
                    status: monthendStatus,
                    closedAt: monthendClosedAt,
                    closedByKnown: false,
                  }
                : undefined
            }
            canLock={canLock}
            canUnlock={canUnlock}
            isLocking={lockMutation.isPending}
            isUnlocking={unlockMutation.isPending}
            onSoftClose={() =>
              setPendingDialogAction({
                action: "lock",
                lockType: "SOFT_CLOSED",
              })
            }
            onHardClose={() =>
              setPendingDialogAction({
                action: "lock",
                lockType: "HARD_CLOSED",
              })
            }
            onUnlock={() => setPendingDialogAction({ action: "unlock" })}
          />

          <section className="grid gap-4 lg:grid-cols-[1.2fr_0.8fr]">
            <div className="rounded-2xl border border-border bg-card p-5">
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div>
                  <p className="text-xs uppercase tracking-wide text-muted-foreground">Month-end record</p>
                  <h2 className="mt-1 text-lg font-semibold text-foreground">
                    {activeEntity?.entity_name ?? "Active entity"} checklist
                  </h2>
                  <p className="mt-1 text-sm text-muted-foreground">
                    Data source is `/api/v1/monthend/*` when available. Close actions remain on the legacy
                    period lock API because that is still the truthful backend contract.
                  </p>
                </div>
                {currentMonthendChecklist ? (
                  <span className="rounded-full border border-border px-3 py-1 text-xs text-foreground">
                    {currentMonthendChecklist.status}
                  </span>
                ) : (
                  <span className="rounded-full border border-border px-3 py-1 text-xs text-muted-foreground">
                    No checklist found
                  </span>
                )}
              </div>

              {monthendDetailQuery.isLoading ? (
                <p className="mt-4 text-sm text-muted-foreground">Loading month-end checklist...</p>
              ) : monthendDetailQuery.error ? (
                <p className="mt-4 text-sm text-[hsl(var(--brand-danger))]">
                  Month-end detail could not be loaded. The list record is still visible.
                </p>
              ) : currentMonthendChecklist ? (
                <div className="mt-4 space-y-4">
                  <div className="space-y-2">
                    <div className="flex items-center justify-between text-sm">
                      <span className="text-muted-foreground">Task progress</span>
                      <span className="font-medium text-foreground">
                        {completedTasks} / {checklistTasks.length} completed
                      </span>
                    </div>
                    <div className="h-2 overflow-hidden rounded-full bg-muted">
                      <div
                        className="h-full rounded-full bg-[hsl(var(--brand-primary))]"
                        style={{ width: `${checklistProgress}%` }}
                      />
                    </div>
                  </div>
                  <div className="grid gap-3 md:grid-cols-2">
                    <div className="rounded-xl border border-border bg-background p-3">
                      <p className="text-xs uppercase tracking-wide text-muted-foreground">Created at</p>
                      <p className="mt-1 text-sm text-foreground">{currentMonthendChecklist.created_at}</p>
                    </div>
                    <div className="rounded-xl border border-border bg-background p-3">
                      <p className="text-xs uppercase tracking-wide text-muted-foreground">Closed at</p>
                      <p className="mt-1 text-sm text-foreground">{monthendClosedAt ?? "Not closed yet"}</p>
                    </div>
                  </div>
                  <div className="rounded-xl border border-border bg-background p-3">
                    <p className="text-xs uppercase tracking-wide text-muted-foreground">Closed by</p>
                    <p className="mt-1 text-sm text-foreground">
                      Not exposed by the current month-end API
                    </p>
                  </div>
                  <div className="flex flex-wrap items-center gap-2">
                  <Button
                    type="button"
                    variant="outline"
                    disabled={
                      closeChecklistMutation.isPending ||
                      monthendStatus.toLowerCase() === "closed" ||
                      !currentMonthendChecklist
                    }
                    onClick={() => setShowCloseChecklistDialog(true)}
                  >
                    Close Checklist
                  </Button>
                    <Button type="button" variant="ghost" asChild>
                      <Link href={`/close/checklist?period=${period}`}>Open Checklist Detail</Link>
                    </Button>
                  </div>
                </div>
              ) : (
                <p className="mt-4 text-sm text-muted-foreground">
                  No month-end checklist exists for this entity and period yet.
                </p>
              )}
            </div>

            <div className="rounded-2xl border border-border bg-card p-5">
              <h3 className="text-base font-semibold text-foreground">Governance status</h3>
              <div className="mt-4 space-y-3 text-sm">
                <div className="rounded-xl border border-border bg-background p-3">
                  <p className="text-xs uppercase tracking-wide text-muted-foreground">Checklist state</p>
                  <p className="mt-1 text-foreground">{monthendStatus}</p>
                </div>
                <div className="rounded-xl border border-border bg-background p-3">
                  <p className="text-xs uppercase tracking-wide text-muted-foreground">Checklist progress</p>
                  <p className="mt-1 text-foreground">
                    {currentMonthendChecklist
                      ? `${completedTasks} of ${checklistTasks.length} tasks complete`
                      : "No month-end checklist loaded"}
                  </p>
                </div>
                <div className="rounded-xl border border-border bg-background p-3">
                  <p className="text-xs uppercase tracking-wide text-muted-foreground">Backend note</p>
                  <p className="mt-1 text-foreground">
                    {periodQuery.data?.locked_by
                      ? "Locked-by attribution is available on the legacy period endpoint."
                      : "Attribution remains partial where the backend does not expose it."}
                  </p>
                </div>
              </div>
            </div>
          </section>

          <ApprovalGraph
            title="Close governance path"
            description="A structured view of readiness, lock state, and month-end checklist completion."
            stages={approvalStages}
            footerNote="Month-end checklist close emits closed_at, but closed_by is not exposed by the current API."
          />
        </>
      )}

      <LockReasonDialog
        open={Boolean(pendingDialogAction)}
        action={pendingDialogAction?.action ?? "lock"}
        onConfirm={handleDialogConfirm}
        onCancel={() => setPendingDialogAction(null)}
      />

      <ChecklistCloseDialog
        open={showCloseChecklistDialog}
        checklistLabel={currentMonthendChecklist ? `${currentMonthendChecklist.entity_name} ${period}` : "month-end checklist"}
        onConfirm={(notes) => {
          if (!currentMonthendChecklist) {
            setShowCloseChecklistDialog(false)
            return
          }
          closeChecklistMutation.mutate(
            { notes },
            {
              onSettled: () => setShowCloseChecklistDialog(false),
            },
          )
        }}
        onCancel={() => setShowCloseChecklistDialog(false)}
      />
    </div>
  )
}
