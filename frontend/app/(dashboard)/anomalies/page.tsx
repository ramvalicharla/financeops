"use client"

import Link from "next/link"
import { useCallback, useEffect, useMemo, useState } from "react"
import { AlertTriangle, Loader2 } from "lucide-react"
import { Button } from "@/components/ui/button"
import {
  fetchAnomalyAlerts,
  updateAnomalyStatus,
} from "@/lib/api/anomaly"
import type { AnomalyAlert, AnomalyStatus } from "@/lib/types/anomaly"
import { cn } from "@/lib/utils"

const severityOptions = ["ALL", "LOW", "MEDIUM", "HIGH", "CRITICAL"] as const
const statusOptions = ["OPEN", "SNOOZED", "RESOLVED", "ESCALATED"] as const

const severityBadgeClass = (severity: string): string => {
  const normalized = severity.toUpperCase()
  if (normalized === "CRITICAL") return "bg-red-500/20 text-red-300"
  if (normalized === "HIGH") return "bg-orange-500/20 text-orange-300"
  if (normalized === "MEDIUM") return "bg-yellow-500/20 text-yellow-300"
  if (normalized === "LOW") return "bg-slate-500/20 text-slate-300"
  return "bg-blue-500/20 text-blue-300"
}

const statusBadgeClassMap: Record<AnomalyStatus, string> = {
  OPEN: "bg-red-500/20 text-red-300",
  SNOOZED: "bg-yellow-500/20 text-yellow-300",
  RESOLVED: "bg-[hsl(var(--brand-success)/0.2)] text-[hsl(var(--brand-success))]",
  ESCALATED: "bg-purple-500/20 text-purple-300",
}

const formatDateTime = (value: string | null): string => {
  if (!value) return "-"
  const parsed = new Date(value)
  return Number.isNaN(parsed.getTime()) ? value : parsed.toLocaleString()
}

interface SnoozeDialogState {
  alertId: string
  selectedDate: string
}

function SnoozeDialog({
  state,
  submitting,
  error,
  onClose,
  onDateChange,
  onSubmit,
}: {
  state: SnoozeDialogState | null
  submitting: boolean
  error: string | null
  onClose: () => void
  onDateChange: (value: string) => void
  onSubmit: () => void
}) {
  if (!state) return null
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4">
      <div className="w-full max-w-md rounded-lg border border-border bg-card p-5">
        <div className="flex items-center justify-between">
          <h2 className="text-lg font-semibold text-foreground">Snooze Alert</h2>
          <Button type="button" variant="outline" onClick={onClose} disabled={submitting}>
            Close
          </Button>
        </div>
        <div className="mt-4 space-y-3">
          <label className="space-y-1 text-sm text-foreground" htmlFor="snooze-until">
            <span>Snooze Until</span>
            <input
              id="snooze-until"
              type="date"
              value={state.selectedDate}
              onChange={(event) => onDateChange(event.target.value)}
              className="w-full rounded-md border border-border bg-background px-3 py-2 text-sm text-foreground"
            />
          </label>
          {error ? (
            <p className="rounded-md border border-destructive/40 bg-destructive/10 px-3 py-2 text-sm text-destructive">
              {error}
            </p>
          ) : null}
        </div>
        <div className="mt-5 flex justify-end gap-2">
          <Button type="button" variant="outline" onClick={onClose} disabled={submitting}>
            Cancel
          </Button>
          <Button type="button" onClick={onSubmit} disabled={submitting}>
            {submitting ? (
              <>
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                Saving...
              </>
            ) : (
              "Save Snooze"
            )}
          </Button>
        </div>
      </div>
    </div>
  )
}

export default function AnomaliesPage() {
  const [alerts, setAlerts] = useState<AnomalyAlert[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [updatingId, setUpdatingId] = useState<string | null>(null)
  const [severityFilter, setSeverityFilter] = useState<(typeof severityOptions)[number]>("ALL")
  const [categoryFilter, setCategoryFilter] = useState("ALL")
  const [statusFilter, setStatusFilter] = useState<AnomalyStatus>("OPEN")
  const [snoozeState, setSnoozeState] = useState<SnoozeDialogState | null>(null)
  const [snoozeError, setSnoozeError] = useState<string | null>(null)

  const categoryOptions = useMemo(() => {
    const values = new Set<string>()
    for (const alert of alerts) {
      values.add(alert.category)
    }
    return ["ALL", ...Array.from(values).sort((left, right) => left.localeCompare(right))]
  }, [alerts])

  const loadAlerts = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const rows = await fetchAnomalyAlerts({
        severity: severityFilter,
        category: categoryFilter,
        status: statusFilter,
        limit: 50,
      })
      setAlerts(rows)
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Failed to load anomalies.")
      setAlerts([])
    } finally {
      setLoading(false)
    }
  }, [categoryFilter, severityFilter, statusFilter])

  useEffect(() => {
    void loadAlerts()
  }, [loadAlerts])

  const updateStatus = async (
    alertId: string,
    nextStatus: Exclude<AnomalyStatus, "OPEN">,
    snoozedUntil?: string,
  ) => {
    setUpdatingId(alertId)
    setError(null)
    try {
      await updateAnomalyStatus(alertId, {
        status: nextStatus,
        snoozed_until: snoozedUntil,
      })
      await loadAlerts()
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Failed to update alert status.")
    } finally {
      setUpdatingId(null)
    }
  }

  const openSnoozeDialog = (alertId: string) => {
    setSnoozeState({
      alertId,
      selectedDate: new Date().toISOString().slice(0, 10),
    })
    setSnoozeError(null)
  }

  const submitSnooze = async () => {
    if (!snoozeState) return
    if (!snoozeState.selectedDate) {
      setSnoozeError("Select a snooze-until date.")
      return
    }
    await updateStatus(snoozeState.alertId, "SNOOZED", snoozeState.selectedDate)
    setSnoozeState(null)
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold text-foreground">Anomaly Detection</h1>
        <p className="text-sm text-muted-foreground">
          Review anomaly alerts and manage operational status.
        </p>
      </div>
      <div>
        <Button asChild type="button" variant="outline">
          <Link href="/anomalies/thresholds">Thresholds</Link>
        </Button>
      </div>

      <section className="rounded-lg border border-border bg-card p-4">
        <div className="mb-4 grid gap-3 md:grid-cols-3">
          <label className="space-y-1 text-sm text-foreground" htmlFor="anomaly-severity-filter">
            <span>Severity</span>
            <select
              id="anomaly-severity-filter"
              className="w-full rounded-md border border-border bg-background px-3 py-2 text-sm"
              value={severityFilter}
              onChange={(event) =>
                setSeverityFilter(event.target.value as (typeof severityOptions)[number])
              }
            >
              {severityOptions.map((value) => (
                <option key={value} value={value}>
                  {value}
                </option>
              ))}
            </select>
          </label>
          <label className="space-y-1 text-sm text-foreground" htmlFor="anomaly-category-filter">
            <span>Category</span>
            <select
              id="anomaly-category-filter"
              className="w-full rounded-md border border-border bg-background px-3 py-2 text-sm"
              value={categoryFilter}
              onChange={(event) => setCategoryFilter(event.target.value)}
            >
              {categoryOptions.map((value) => (
                <option key={value} value={value}>
                  {value}
                </option>
              ))}
            </select>
          </label>
          <label className="space-y-1 text-sm text-foreground" htmlFor="anomaly-status-filter">
            <span>Status</span>
            <select
              id="anomaly-status-filter"
              className="w-full rounded-md border border-border bg-background px-3 py-2 text-sm"
              value={statusFilter}
              onChange={(event) => setStatusFilter(event.target.value as AnomalyStatus)}
            >
              {statusOptions.map((value) => (
                <option key={value} value={value}>
                  {value}
                </option>
              ))}
            </select>
          </label>
        </div>

        {error ? (
          <p className="mb-3 rounded-md border border-destructive/40 bg-destructive/10 px-3 py-2 text-sm text-destructive">
            {error}
          </p>
        ) : null}

        {loading ? (
          <div className="h-32 animate-pulse rounded-md border border-border bg-muted/30" />
        ) : null}

        {!loading && !alerts.length ? (
          <div className="rounded-md border border-border bg-muted/20 px-4 py-8 text-center">
            <AlertTriangle className="mx-auto mb-3 h-8 w-8 text-muted-foreground" />
            <p className="text-sm text-muted-foreground">No anomalies detected.</p>
          </div>
        ) : null}

        {!!alerts.length ? (
          <div className="overflow-x-auto rounded-md border border-border">
            <table className="w-full min-w-[1080px] text-sm">
              <thead>
                <tr className="bg-muted/30">
                  <th className="px-3 py-2 text-left font-medium text-foreground">Type</th>
                  <th className="px-3 py-2 text-left font-medium text-foreground">Severity</th>
                  <th className="px-3 py-2 text-left font-medium text-foreground">Category</th>
                  <th className="px-3 py-2 text-left font-medium text-foreground">Detected</th>
                  <th className="px-3 py-2 text-left font-medium text-foreground">Status</th>
                  <th className="px-3 py-2 text-left font-medium text-foreground">Actions</th>
                </tr>
              </thead>
              <tbody>
                {alerts.map((alert) => (
                  <tr key={alert.id} className="border-t border-border">
                    <td className="px-3 py-2 text-muted-foreground">{alert.alert_type}</td>
                    <td className="px-3 py-2">
                      <span
                        className={cn(
                          "inline-flex rounded-full px-2 py-1 text-xs font-medium",
                          severityBadgeClass(alert.severity),
                        )}
                      >
                        {alert.severity.toUpperCase()}
                      </span>
                    </td>
                    <td className="px-3 py-2 text-muted-foreground">{alert.category}</td>
                    <td className="px-3 py-2 text-muted-foreground">
                      {formatDateTime(alert.detected_at)}
                    </td>
                    <td className="px-3 py-2">
                      <span
                        className={cn(
                          "inline-flex rounded-full px-2 py-1 text-xs font-medium",
                          statusBadgeClassMap[alert.alert_status],
                        )}
                      >
                        {alert.alert_status}
                      </span>
                    </td>
                    <td className="px-3 py-2">
                      <div className="flex flex-wrap gap-2">
                        <Button asChild size="sm" variant="outline">
                          <Link href={`/anomalies/${alert.id}`}>View</Link>
                        </Button>
                        <Button
                          type="button"
                          size="sm"
                          variant="outline"
                          disabled={updatingId === alert.id || alert.alert_status !== "OPEN"}
                          onClick={() => {
                            void updateStatus(alert.id, "RESOLVED")
                          }}
                        >
                          Resolve
                        </Button>
                        <Button
                          type="button"
                          size="sm"
                          variant="outline"
                          disabled={updatingId === alert.id || alert.alert_status !== "OPEN"}
                          onClick={() => openSnoozeDialog(alert.id)}
                        >
                          Snooze
                        </Button>
                        <Button
                          type="button"
                          size="sm"
                          variant="outline"
                          disabled={updatingId === alert.id || alert.alert_status !== "OPEN"}
                          onClick={() => {
                            void updateStatus(alert.id, "ESCALATED")
                          }}
                        >
                          Escalate
                        </Button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : null}
      </section>

      <SnoozeDialog
        state={snoozeState}
        submitting={updatingId === snoozeState?.alertId}
        error={snoozeError}
        onClose={() => setSnoozeState(null)}
        onDateChange={(value) =>
          setSnoozeState((previous) =>
            previous ? { ...previous, selectedDate: value } : previous,
          )
        }
        onSubmit={() => {
          void submitSnooze()
        }}
      />
    </div>
  )
}
