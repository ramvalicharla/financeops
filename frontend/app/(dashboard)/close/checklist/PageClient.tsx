"use client"

import Link from "next/link"
import { useMemo, useState } from "react"
import { useSearchParams } from "next/navigation"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import {
  closeMonthendChecklist,
  getMonthendChecklist,
  getMonthendChecklists,
  runReadiness,
  updateMonthendChecklistTaskStatus,
  type MonthendChecklistTask,
} from "@/lib/api/close-governance"
import { useTenantStore } from "@/lib/store/tenant"
import { useWorkspaceStore } from "@/lib/store/workspace"
import { queryKeys } from "@/lib/query/keys"
import { StateBadge } from "@/components/ui"
import { Button } from "@/components/ui/button"
import { ChecklistCloseDialog } from "../_components/ChecklistCloseDialog"
import { ApprovalGraph } from "../_components/ApprovalGraph"

const parsePeriod = (value: string): { fiscalYear: number; periodNumber: number } => {
  const [yearText, monthText] = value.split("-")
  const fiscalYear = Number.parseInt(yearText, 10)
  const periodNumber = Number.parseInt(monthText, 10)
  return {
    fiscalYear: Number.isFinite(fiscalYear) ? fiscalYear : new Date().getFullYear(),
    periodNumber: Number.isFinite(periodNumber) ? periodNumber : new Date().getMonth() + 1,
  }
}

const normalize = (value: string): string => value.trim().toLowerCase().replace(/\s+/g, "_")

export default function CloseChecklistPage() {
  const queryClient = useQueryClient()
  const searchParams = useSearchParams()
  const entityId = useWorkspaceStore((s) => s.entityId)
  const entityRoles = useTenantStore((state) => state.entity_roles)
  const initialPeriod = searchParams?.get("period") ?? new Date().toISOString().slice(0, 7)
  const [period, setPeriod] = useState(initialPeriod)
  const [showCloseDialog, setShowCloseDialog] = useState(false)
  const { fiscalYear, periodNumber } = useMemo(() => parsePeriod(period), [period])
  const activeEntity = useMemo(
    () => entityRoles.find((role) => role.entity_id === entityId) ?? null,
    [entityId, entityRoles],
  )

  const monthendListQuery = useQuery({
    queryKey: queryKeys.close.monthendList(activeEntity?.entity_name ?? null),
    queryFn: async () =>
      getMonthendChecklists({
        entity_name: activeEntity?.entity_name ?? undefined,
        limit: 24,
      }),
    enabled: Boolean(activeEntity?.entity_name),
  })

  const currentChecklist = useMemo(
    () =>
      monthendListQuery.data?.checklists.find(
        (checklist) =>
          checklist.period_year === fiscalYear && checklist.period_month === periodNumber,
      ) ?? null,
    [fiscalYear, monthendListQuery.data?.checklists, periodNumber],
  )

  const checklistDetailQuery = useQuery({
    queryKey: queryKeys.close.monthendDetail(currentChecklist?.checklist_id ?? null),
    queryFn: async () => (currentChecklist ? getMonthendChecklist(currentChecklist.checklist_id) : null),
    enabled: Boolean(currentChecklist?.checklist_id),
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

  const refresh = async (): Promise<void> => {
    await queryClient.invalidateQueries({ queryKey: queryKeys.close.monthendListAll() })
    await queryClient.invalidateQueries({ queryKey: queryKeys.close.monthendDetailAll() })
    await queryClient.invalidateQueries({ queryKey: queryKeys.close.readinessAll() })
  }

  const updateTaskMutation = useMutation({
    mutationFn: (taskId: string) => {
      if (!currentChecklist) {
        throw new Error("No checklist loaded.")
      }
      return updateMonthendChecklistTaskStatus({
        checklistId: currentChecklist.checklist_id,
        taskId,
        status: "completed",
      })
    },
    onSuccess: refresh,
  })

  const closeMutation = useMutation({
    mutationFn: (notes: string) => {
      if (!currentChecklist) {
        throw new Error("No checklist loaded.")
      }
      return closeMonthendChecklist({
        checklistId: currentChecklist.checklist_id,
        notes,
      })
    },
    onSuccess: refresh,
  })

  const checklistTasks: MonthendChecklistTask[] = checklistDetailQuery.data?.tasks ?? []
  const completedTasks = checklistTasks.filter((task) => normalize(task.status) === "completed").length
  const totalTasks = checklistTasks.length
  const progress = totalTasks ? Math.round((completedTasks / totalTasks) * 100) : 0
  const isClosed = normalize(checklistDetailQuery.data?.status ?? currentChecklist?.status ?? "") === "closed"

  const approvalStages = [
    ...(checklistTasks
      .slice()
      .sort((left, right) => left.sort_order - right.sort_order)
      .map((task) => ({
        id: task.task_id,
        label: task.task_name,
        status: task.status,
        detail: `${task.task_category} - ${task.priority}`,
        completedAt: task.completed_at,
      })) ?? []),
    {
      id: "close",
      label: "Checklist close",
      status: isClosed ? "closed" : "open",
      detail: isClosed
        ? "The checklist has been closed in the backend."
        : "Checklist close is still pending.",
      completedAt: checklistDetailQuery.data?.closed_at ?? null,
    },
  ]

  return (
    <div className="space-y-6 p-6">
      <header className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold text-foreground">Close Checklist</h1>
          <p className="text-sm text-muted-foreground">
            Month-end checklist tasks, completion progress, and close-state evidence.
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
            <Link href={`/close?period=${period}`}>Back to Close</Link>
          </Button>
        </div>
      </header>

      {!entityId ? (
        <section className="rounded-xl border border-border bg-card p-5">
          <p className="text-sm text-muted-foreground">Select an active entity to load checklist items.</p>
        </section>
      ) : monthendListQuery.isLoading || checklistDetailQuery.isLoading ? (
        <section className="rounded-xl border border-border bg-card p-5">
          <p className="text-sm text-muted-foreground">Loading month-end checklist...</p>
        </section>
      ) : monthendListQuery.error ? (
        <section className="rounded-xl border border-border bg-card p-5">
          <p className="text-sm text-[hsl(var(--brand-danger))]">Failed to load month-end checklist.</p>
        </section>
      ) : checklistDetailQuery.error ? (
        <section className="rounded-xl border border-border bg-card p-5">
          <p className="text-sm text-[hsl(var(--brand-danger))]">
            Month-end checklist details could not be loaded. The checklist record list is still available.
          </p>
        </section>
      ) : (
        <>
          <section className="grid gap-4 lg:grid-cols-[1.15fr_0.85fr]">
            <div className="rounded-2xl border border-border bg-card p-5">
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div>
                  <p className="text-xs uppercase tracking-wide text-muted-foreground">Month-end record</p>
                  <h2 className="mt-1 text-lg font-semibold text-foreground">
                    {activeEntity?.entity_name ?? "Active entity"} {period}
                  </h2>
                  <p className="mt-1 text-sm text-muted-foreground">
                    The checklist view is now backed by `/api/v1/monthend/*`. The legacy close readiness
                    endpoint still supplies blockers and warnings for honest governance context.
                  </p>
                </div>
                <StateBadge
                  status={checklistDetailQuery.data?.status ?? currentChecklist?.status ?? "missing"}
                  label={checklistDetailQuery.data?.status ?? currentChecklist?.status ?? "missing"}
                />
              </div>

              <div className="mt-5 space-y-3">
                <div className="space-y-2">
                  <div className="flex items-center justify-between text-sm">
                    <span className="text-muted-foreground">Task progress</span>
                    <span className="font-medium text-foreground">
                      {completedTasks} of {totalTasks} tasks complete
                    </span>
                  </div>
                  <div className="h-2 overflow-hidden rounded-full bg-muted">
                    <div
                      className="h-full rounded-full bg-[hsl(var(--brand-primary))]"
                      style={{ width: `${progress}%` }}
                    />
                  </div>
                </div>
                <div className="grid gap-3 md:grid-cols-2">
                  <div className="rounded-xl border border-border bg-background p-3">
                    <p className="text-xs uppercase tracking-wide text-muted-foreground">Created at</p>
                    <p className="mt-1 text-sm text-foreground">
                      {currentChecklist?.created_at ?? "Not available"}
                    </p>
                  </div>
                  <div className="rounded-xl border border-border bg-background p-3">
                    <p className="text-xs uppercase tracking-wide text-muted-foreground">Closed at</p>
                    <p className="mt-1 text-sm text-foreground">
                      {checklistDetailQuery.data?.closed_at ?? "Not closed yet"}
                    </p>
                  </div>
                </div>
                <div className="rounded-xl border border-border bg-background p-3">
                  <p className="text-xs uppercase tracking-wide text-muted-foreground">Closed by</p>
                  <p className="mt-1 text-sm text-foreground">Not exposed by the current month-end API</p>
                </div>
                <div className="flex flex-wrap items-center gap-2">
                  <Button
                    type="button"
                    variant="outline"
                    disabled={closeMutation.isPending || isClosed || !currentChecklist}
                    onClick={() => setShowCloseDialog(true)}
                  >
                    Close Checklist
                  </Button>
                    <Button type="button" variant="ghost" asChild>
                      <Link href={`/close?period=${period}`}>Return to Close Cockpit</Link>
                    </Button>
                </div>
              </div>
            </div>

            <section className="rounded-2xl border border-border bg-card p-5">
              <h3 className="text-base font-semibold text-foreground">Readiness Summary</h3>
              {!entityId ? (
                <p className="mt-2 text-sm text-muted-foreground">Select an active entity to run readiness checks.</p>
              ) : readinessQuery.isLoading ? (
                <p className="mt-2 text-sm text-muted-foreground">Running readiness checks...</p>
              ) : readinessQuery.error ? (
                <p className="mt-2 text-sm text-[hsl(var(--brand-danger))]">Readiness check failed.</p>
              ) : (
                <div className="mt-3 space-y-3">
                  <p className="text-sm text-foreground">
                    Status:{" "}
                    <span className={readinessQuery.data?.pass ? "text-emerald-400" : "text-amber-400"}>
                      {readinessQuery.data?.pass ? "PASS" : "FAIL"}
                    </span>
                  </p>
                  <div>
                    <p className="text-sm font-medium text-foreground">Blockers</p>
                    {readinessQuery.data?.blockers.length ? (
                      <ul className="ml-5 list-disc text-sm text-[hsl(var(--brand-danger))]">
                        {readinessQuery.data.blockers.map((item) => (
                          <li key={item}>{item}</li>
                        ))}
                      </ul>
                    ) : (
                      <p className="text-sm text-muted-foreground">No blockers.</p>
                    )}
                  </div>
                  <div>
                    <p className="text-sm font-medium text-foreground">Warnings</p>
                    {readinessQuery.data?.warnings.length ? (
                      <ul className="ml-5 list-disc text-sm text-amber-300">
                        {readinessQuery.data.warnings.map((item) => (
                          <li key={item}>{item}</li>
                        ))}
                      </ul>
                    ) : (
                      <p className="text-sm text-muted-foreground">No warnings.</p>
                    )}
                  </div>
                </div>
              )}
            </section>
          </section>

          <ApprovalGraph
            title="Checklist approval path"
            description="Month-end checklist tasks are shown in execution order, with the close action shown as the final governed step."
            stages={approvalStages}
            footerNote="Closed-by attribution is not exposed by the month-end checklist API, so the graph keeps that limitation explicit."
          />

          <section className="overflow-hidden rounded-xl border border-border bg-card">
            <div className="overflow-x-auto">
              <table className="min-w-full divide-y divide-border text-sm">
                <thead className="bg-muted/30">
                  <tr className="text-left text-xs uppercase tracking-wide text-muted-foreground">
                    <th className="px-4 py-2">Checklist Item</th>
                    <th className="px-4 py-2">Category</th>
                    <th className="px-4 py-2">Priority</th>
                    <th className="px-4 py-2">Status</th>
                    <th className="px-4 py-2">Completed At</th>
                    <th className="px-4 py-2">Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border">
                  {checklistTasks.map((item) => (
                    <tr key={item.task_id}>
                      <td className="px-4 py-2 text-foreground">{item.task_name}</td>
                      <td className="px-4 py-2 text-muted-foreground">{item.task_category}</td>
                      <td className="px-4 py-2 text-muted-foreground">{item.priority}</td>
                      <td className="px-4 py-2">
                        <StateBadge status={item.status} label={item.status} />
                      </td>
                      <td className="px-4 py-2 text-muted-foreground">{item.completed_at ?? "-"}</td>
                      <td className="px-4 py-2">
                        <Button
                          variant="outline"
                          disabled={normalize(item.status) === "completed" || updateTaskMutation.isPending}
                          onClick={() => updateTaskMutation.mutate(item.task_id)}
                        >
                          Mark Complete
                        </Button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>
        </>
      )}

      <ChecklistCloseDialog
        open={showCloseDialog}
        checklistLabel={currentChecklist ? `${currentChecklist.entity_name} ${period}` : "month-end checklist"}
        onConfirm={(notes) => {
          if (!currentChecklist) {
            setShowCloseDialog(false)
            return
          }
          closeMutation.mutate(notes, {
            onSettled: () => setShowCloseDialog(false),
          })
        }}
        onCancel={() => setShowCloseDialog(false)}
      />
    </div>
  )
}
