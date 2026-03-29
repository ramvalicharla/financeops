"use client"

import { useCallback, useEffect, useMemo, useState } from "react"
import { useRouter } from "next/navigation"
import { useSession } from "next-auth/react"
import { ChecklistBoard } from "@/components/closing/ChecklistBoard"
import { ChecklistTask } from "@/components/closing/ChecklistTask"
import { ProgressRing } from "@/components/closing/ProgressRing"
import {
  assignChecklistTask,
  fetchChecklistForPeriod,
  fetchClosingAnalytics,
  patchChecklistTaskStatus,
} from "@/lib/api/closing"
import type { ChecklistPeriodPayload, ChecklistTaskItem, ClosingAnalytics } from "@/lib/types/closing"

interface ChecklistScreenProps {
  initialPeriod: string
  showPeriodSelector: boolean
  forceReadOnly?: boolean
}

const statusDone = new Set(["completed", "skipped"])
const statusProgress = new Set(["in_progress", "completed", "skipped"])

const makeRecentPeriods = (fromPeriod: string): string[] => {
  const [yearText, monthText] = fromPeriod.split("-")
  const year = Number.parseInt(yearText, 10)
  const month = Number.parseInt(monthText, 10)
  if (!Number.isFinite(year) || !Number.isFinite(month)) {
    return [new Date().toISOString().slice(0, 7)]
  }
  const base = new Date(year, month - 1, 1)
  return Array.from({ length: 4 }).map((_, idx) => {
    const date = new Date(base.getFullYear(), base.getMonth() - idx, 1)
    return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, "0")}`
  })
}

export function ChecklistScreen({ initialPeriod, showPeriodSelector, forceReadOnly = false }: ChecklistScreenProps) {
  const router = useRouter()
  const { data: session } = useSession()
  const [period, setPeriod] = useState(initialPeriod)
  const [payload, setPayload] = useState<ChecklistPeriodPayload | null>(null)
  const [analytics, setAnalytics] = useState<ClosingAnalytics | null>(null)
  const [analyticsOpen, setAnalyticsOpen] = useState(false)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [selectedTask, setSelectedTask] = useState<ChecklistTaskItem | null>(null)

  const periods = useMemo(() => makeRecentPeriods(initialPeriod), [initialPeriod])

  const readOnly = forceReadOnly || payload?.run.status === "completed" || payload?.run.status === "locked"

  const load = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const response = await fetchChecklistForPeriod(period)
      setPayload(response)
    } catch (fetchError) {
      setError(fetchError instanceof Error ? fetchError.message : "Failed to load checklist")
      setPayload(null)
    } finally {
      setLoading(false)
    }
  }, [period])

  useEffect(() => {
    void load()
  }, [load])

  const openAnalytics = async () => {
    if (!analytics) {
      const response = await fetchClosingAnalytics()
      setAnalytics(response)
    }
    setAnalyticsOpen((prev) => !prev)
  }

  const updateTask = async (
    taskId: string,
    status: ChecklistTaskItem["status"],
    notes: string,
  ) => {
    if (!payload) return
    const previous = payload

    const optimisticTasks = payload.tasks.map((task) =>
      task.id === taskId ? { ...task, status, notes } : task,
    )
    const optimisticCompleted = optimisticTasks.filter((task) => statusDone.has(task.status)).length
    setPayload({
      ...payload,
      tasks: optimisticTasks,
      run: {
        ...payload.run,
        completed_count: optimisticCompleted,
      },
    })

    try {
      const result = await patchChecklistTaskStatus(period, taskId, status, notes)
      setPayload((current) => {
        if (!current) return current
        return {
          ...current,
          tasks: current.tasks.map((task) =>
            task.id === taskId
              ? {
                  ...task,
                  status: result.task.status as ChecklistTaskItem["status"],
                  notes: result.task.notes,
                  completed_at: result.task.completed_at,
                }
              : task,
          ),
          run: {
            ...current.run,
            status: result.run.status as ChecklistPeriodPayload["run"]["status"],
            progress_pct: result.run.progress_pct,
            completed_count: current.tasks.filter((task) =>
              statusDone.has(task.id === taskId ? (result.task.status as ChecklistTaskItem["status"]) : task.status),
            ).length,
          },
        }
      })
    } catch (updateError) {
      setPayload(previous)
      setError(updateError instanceof Error ? updateError.message : "Status update failed")
      throw updateError
    }
  }

  const assignTask = async (taskId: string, userId: string) => {
    if (!payload) return
    await assignChecklistTask(period, taskId, userId)
    setPayload((current) => {
      if (!current) return current
      return {
        ...current,
        tasks: current.tasks.map((task) =>
          task.id === taskId ? { ...task, assigned_to: userId } : task,
        ),
      }
    })
  }

  const onPeriodChange = (nextPeriod: string) => {
    setPeriod(nextPeriod)
    if (showPeriodSelector) {
      router.push(`/close/${nextPeriod}`)
    }
  }

  const taskTotal = payload?.run.total_count ?? 12
  const taskCompleted = payload
    ? payload.tasks.filter((task) => statusProgress.has(task.status)).length
    : 0
  const canAssign = (session?.user as { role?: string } | undefined)?.role === "finance_leader"

  return (
    <div className="space-y-6">
      <section className="rounded-xl border border-border bg-card p-5">
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div>
            <h1 className="text-2xl font-semibold text-foreground">Month-End Closing Checklist</h1>
            <p className="text-sm text-muted-foreground">
              Daily close operations for {period}.
            </p>
          </div>
          <div className="flex items-center gap-3">
            {showPeriodSelector ? (
              <select
                aria-label="Period"
                className="rounded-md border border-border bg-background px-3 py-2 text-sm"
                value={period}
                onChange={(event) => onPeriodChange(event.target.value)}
              >
                {periods.map((value) => (
                  <option key={value} value={value}>{value}</option>
                ))}
              </select>
            ) : null}
            <button
              type="button"
              className="rounded-md border border-border px-3 py-2 text-sm text-foreground"
              onClick={() => void openAnalytics()}
            >
              View Analytics
            </button>
          </div>
        </div>

        <div className="mt-6 flex flex-wrap items-center gap-6">
          <ProgressRing completed={taskCompleted} total={taskTotal} />
          <div className="space-y-1 text-sm text-muted-foreground">
            <p>Run status: <span className="text-foreground">{payload?.run.status ?? "loading"}</span></p>
            <p>Progress: <span className="text-foreground">{payload?.run.progress_pct ?? "0.00"}%</span></p>
            <p>Target close date: <span className="text-foreground">{payload?.run.target_close_date ?? "n/a"}</span></p>
          </div>
        </div>
      </section>

      {analyticsOpen && analytics ? (
        <section className="rounded-xl border border-border bg-card p-4 text-sm">
          <div className="grid gap-3 md:grid-cols-3">
            <div>Avg days to close: <strong>{analytics.avg_days_to_close}</strong></div>
            <div>On-time rate: <strong>{analytics.on_time_rate}%</strong></div>
            <div>Trend: <strong>{analytics.trend}</strong></div>
            <div>Fastest period: <strong>{analytics.fastest_close_period ?? "n/a"}</strong></div>
            <div>Slowest period: <strong>{analytics.slowest_close_period ?? "n/a"}</strong></div>
            <div>Most blocked task: <strong>{analytics.most_blocked_task ?? "n/a"}</strong></div>
          </div>
        </section>
      ) : null}

      {error ? (
        <p className="rounded-md border border-[hsl(var(--brand-danger)/0.4)] bg-[hsl(var(--brand-danger)/0.15)] px-4 py-3 text-sm text-[hsl(var(--brand-danger))]">
          {error}
        </p>
      ) : null}

      <ChecklistBoard
        tasks={payload?.tasks ?? []}
        loading={loading}
        readOnly={Boolean(readOnly)}
        onOpenTask={setSelectedTask}
      />

      <ChecklistTask
        open={selectedTask !== null}
        task={selectedTask}
        allTasks={payload?.tasks ?? []}
        canAssign={Boolean(canAssign)}
        readOnly={Boolean(readOnly)}
        onClose={() => setSelectedTask(null)}
        onSave={updateTask}
        onAssign={assignTask}
      />
    </div>
  )
}
