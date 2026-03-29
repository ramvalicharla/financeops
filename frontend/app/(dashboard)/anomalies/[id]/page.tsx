"use client"

import Link from "next/link"
import { useParams } from "next/navigation"
import { useCallback, useEffect, useMemo, useState } from "react"
import { Loader2 } from "lucide-react"
import { Button } from "@/components/ui/button"
import { fetchAnomalyAlert, updateAnomalyStatus } from "@/lib/api/anomaly"
import type { AnomalyAlert, AnomalyStatus } from "@/lib/types/anomaly"
import { cn } from "@/lib/utils"

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

interface SnoozeState {
  selectedDate: string
}

export default function AnomalyDetailPage() {
  const params = useParams<{ id: string }>()
  const alertId = params?.id ?? ""

  const [alert, setAlert] = useState<AnomalyAlert | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [updating, setUpdating] = useState(false)
  const [snoozeState, setSnoozeState] = useState<SnoozeState | null>(null)

  const loadAlert = useCallback(async () => {
    if (!alertId) return
    setLoading(true)
    setError(null)
    try {
      setAlert(await fetchAnomalyAlert(alertId))
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Failed to load anomaly alert.")
      setAlert(null)
    } finally {
      setLoading(false)
    }
  }, [alertId])

  useEffect(() => {
    void loadAlert()
  }, [loadAlert])

  const updateStatus = async (
    nextStatus: Exclude<AnomalyStatus, "OPEN">,
    snoozedUntil?: string,
  ) => {
    if (!alertId) return
    setUpdating(true)
    setError(null)
    try {
      const updated = await updateAnomalyStatus(alertId, {
        status: nextStatus,
        snoozed_until: snoozedUntil,
      })
      setAlert(updated)
      setSnoozeState(null)
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Failed to update anomaly status.")
    } finally {
      setUpdating(false)
    }
  }

  const detailRows = useMemo(() => {
    if (!alert) return []
    return [
      ["Alert ID", alert.id],
      ["Rule Code", alert.rule_code],
      ["Run ID", alert.run_id],
      ["Line No", String(alert.line_no)],
      ["Category", alert.category],
      ["Severity", alert.severity.toUpperCase()],
      ["Anomaly Score", String(alert.anomaly_score)],
      ["Confidence Score", String(alert.confidence_score)],
      ["Persistence", alert.persistence_classification],
      ["Correlation Flag", String(alert.correlation_flag)],
      ["Materiality Elevated", String(alert.materiality_elevated)],
      ["Risk Elevated", String(alert.risk_elevated)],
      ["Board Flag", String(alert.board_flag)],
      ["Detected At", formatDateTime(alert.detected_at)],
      ["Created At", formatDateTime(alert.created_at)],
      ["Status", alert.alert_status],
      ["Snoozed Until", formatDateTime(alert.snoozed_until)],
      ["Resolved At", formatDateTime(alert.resolved_at)],
      ["Escalated At", formatDateTime(alert.escalated_at)],
    ] as Array<[string, string]>
  }, [alert])

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-2">
        <Button type="button" variant="outline" asChild>
          <Link href="/anomalies">Back</Link>
        </Button>
      </div>

      {loading ? <div className="h-40 animate-pulse rounded-lg border border-border bg-card" /> : null}

      {error ? (
        <p className="rounded-md border border-destructive/40 bg-destructive/10 px-3 py-2 text-sm text-destructive">
          {error}
        </p>
      ) : null}

      {alert ? (
        <>
          <section className="rounded-lg border border-border bg-card p-4">
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div className="space-y-2">
                <h1 className="text-2xl font-semibold text-foreground">{alert.alert_type}</h1>
                <p className="text-sm text-muted-foreground">
                  Detected at {formatDateTime(alert.detected_at)}
                </p>
                <div className="flex flex-wrap gap-2">
                  <span
                    className={cn(
                      "inline-flex rounded-full px-2 py-1 text-xs font-medium",
                      severityBadgeClass(alert.severity),
                    )}
                  >
                    {alert.severity.toUpperCase()}
                  </span>
                  <span
                    className={cn(
                      "inline-flex rounded-full px-2 py-1 text-xs font-medium",
                      statusBadgeClassMap[alert.alert_status],
                    )}
                  >
                    {alert.alert_status}
                  </span>
                </div>
              </div>

              <div className="flex flex-wrap gap-2">
                {alert.alert_status === "OPEN" ? (
                  <>
                    <Button
                      type="button"
                      variant="outline"
                      disabled={updating}
                      onClick={() => {
                        void updateStatus("RESOLVED")
                      }}
                    >
                      Resolve
                    </Button>
                    <Button
                      type="button"
                      variant="outline"
                      disabled={updating}
                      onClick={() =>
                        setSnoozeState({
                          selectedDate: new Date().toISOString().slice(0, 10),
                        })
                      }
                    >
                      Snooze
                    </Button>
                    <Button
                      type="button"
                      variant="outline"
                      disabled={updating}
                      onClick={() => {
                        void updateStatus("ESCALATED")
                      }}
                    >
                      Escalate
                    </Button>
                  </>
                ) : null}
                {alert.alert_status === "SNOOZED" ? (
                  <>
                    <Button
                      type="button"
                      variant="outline"
                      disabled={updating}
                      onClick={() => {
                        void updateStatus("RESOLVED")
                      }}
                    >
                      Resolve
                    </Button>
                    <span className="inline-flex items-center rounded-md border border-border px-3 py-2 text-xs text-muted-foreground">
                      Unsnoozed on {formatDateTime(alert.snoozed_until)}
                    </span>
                  </>
                ) : null}
                {alert.alert_status === "RESOLVED" || alert.alert_status === "ESCALATED" ? (
                  <span className="inline-flex items-center rounded-md border border-border px-3 py-2 text-xs text-muted-foreground">
                    Status is read-only after {alert.alert_status.toLowerCase()}.
                  </span>
                ) : null}
              </div>
            </div>
          </section>

          <section className="rounded-lg border border-border bg-card p-4">
            <h2 className="mb-3 text-lg font-semibold text-foreground">Details</h2>
            <div className="overflow-x-auto rounded-md border border-border">
              <table className="w-full text-sm">
                <tbody>
                  {detailRows.map(([label, value]) => (
                    <tr key={label} className="border-t border-border first:border-t-0">
                      <td className="w-56 px-3 py-2 font-medium text-foreground">{label}</td>
                      <td className="px-3 py-2 text-muted-foreground">{value || "-"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>

          {alert.source_table || alert.source_row_id ? (
            <section className="rounded-lg border border-border bg-card p-4">
              <h2 className="mb-2 text-lg font-semibold text-foreground">Source Reference</h2>
              <p className="text-sm text-muted-foreground">
                Source: {alert.source_table ?? "unknown"} row {alert.source_row_id ?? "unknown"}
              </p>
            </section>
          ) : null}

          <section className="rounded-lg border border-border bg-card p-4">
            <h2 className="mb-2 text-lg font-semibold text-foreground">Status History</h2>
            {alert.status_note || alert.status_updated_by ? (
              <div className="rounded-md border border-border bg-background px-3 py-2 text-sm text-muted-foreground">
                <p>
                  <span className="font-medium text-foreground">Note:</span>{" "}
                  {alert.status_note ?? "-"}
                </p>
                <p>
                  <span className="font-medium text-foreground">Updated By:</span>{" "}
                  {alert.status_updated_by ?? "-"}
                </p>
                <p>
                  <span className="font-medium text-foreground">Updated At:</span>{" "}
                  {formatDateTime(alert.resolved_at ?? alert.escalated_at ?? alert.snoozed_until ?? alert.created_at)}
                </p>
              </div>
            ) : (
              <p className="text-sm text-muted-foreground">No status-history notes.</p>
            )}
          </section>
        </>
      ) : null}

      {snoozeState ? (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4">
          <div className="w-full max-w-md rounded-lg border border-border bg-card p-5">
            <div className="flex items-center justify-between">
              <h2 className="text-lg font-semibold text-foreground">Snooze Alert</h2>
              <Button
                type="button"
                variant="outline"
                onClick={() => setSnoozeState(null)}
                disabled={updating}
              >
                Close
              </Button>
            </div>
            <div className="mt-4 space-y-3">
              <label className="space-y-1 text-sm text-foreground" htmlFor="detail-snooze-until">
                <span>Snooze Until</span>
                <input
                  id="detail-snooze-until"
                  type="date"
                  value={snoozeState.selectedDate}
                  onChange={(event) =>
                    setSnoozeState((previous) =>
                      previous ? { ...previous, selectedDate: event.target.value } : previous,
                    )
                  }
                  className="w-full rounded-md border border-border bg-background px-3 py-2 text-sm text-foreground"
                />
              </label>
            </div>
            <div className="mt-5 flex justify-end gap-2">
              <Button
                type="button"
                variant="outline"
                onClick={() => setSnoozeState(null)}
                disabled={updating}
              >
                Cancel
              </Button>
              <Button
                type="button"
                onClick={() => {
                  void updateStatus("SNOOZED", snoozeState.selectedDate)
                }}
                disabled={updating}
              >
                {updating ? (
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
      ) : null}
    </div>
  )
}
