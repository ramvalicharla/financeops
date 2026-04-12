"use client"

import { useCallback, useEffect, useMemo, useState } from "react"
import { Loader2 } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Dialog } from "@/components/ui/Dialog"
import { Input } from "@/components/ui/input"
import { StructuredDataView } from "@/components/ui"
import {
  fetchAnomalyThresholds,
  updateAnomalyThreshold,
} from "@/lib/api/anomaly"
import type { AnomalyThreshold } from "@/lib/types/anomaly"

interface EditState {
  ruleCode: string
  thresholdValue: string
  configText: string
}

export default function AnomalyThresholdsPage() {
  const [rows, setRows] = useState<AnomalyThreshold[]>([])
  const [loading, setLoading] = useState(false)
  const [savingRule, setSavingRule] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [toastMessage, setToastMessage] = useState<string | null>(null)
  const [editState, setEditState] = useState<EditState | null>(null)

  const loadRows = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const nextRows = await fetchAnomalyThresholds()
      setRows(nextRows)
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Failed to load thresholds.")
      setRows([])
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    void loadRows()
  }, [loadRows])

  useEffect(() => {
    if (!toastMessage) return
    const timeoutId = window.setTimeout(() => setToastMessage(null), 2500)
    return () => window.clearTimeout(timeoutId)
  }, [toastMessage])

  const sortedRows = useMemo(
    () => [...rows].sort((left, right) => left.rule_code.localeCompare(right.rule_code)),
    [rows],
  )

  const startEdit = (row: AnomalyThreshold) => {
    setEditState({
      ruleCode: row.rule_code,
      thresholdValue: row.current_threshold,
      configText: JSON.stringify(row.config ?? {}, null, 2),
    })
  }

  const saveEdit = async () => {
    if (!editState) return
    const thresholdValue = editState.thresholdValue.trim()
    if (!thresholdValue) {
      setError("Threshold value is required.")
      return
    }

    let configPayload: Record<string, unknown>
    try {
      const parsed = JSON.parse(editState.configText || "{}")
      if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) {
        setError("Config must be a JSON object.")
        return
      }
      configPayload = parsed as Record<string, unknown>
    } catch {
      setError("Config JSON is invalid.")
      return
    }

    setSavingRule(editState.ruleCode)
    setError(null)
    try {
      const response = await updateAnomalyThreshold(editState.ruleCode, {
        threshold_value: thresholdValue,
        config: configPayload,
      })
      if (!response.updated) {
        setError(`Rule ${editState.ruleCode} is not active and could not be updated.`)
        return
      }
      await loadRows()
      setEditState(null)
      setToastMessage("Threshold updated.")
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Failed to update threshold.")
    } finally {
      setSavingRule(null)
    }
  }

  return (
    <div className="space-y-6">
      {toastMessage ? (
        <div className="fixed right-4 top-4 z-[60] rounded-md border border-[hsl(var(--brand-success)/0.5)] bg-[hsl(var(--brand-success)/0.2)] px-3 py-2 text-sm text-[hsl(var(--brand-success))]">
          {toastMessage}
        </div>
      ) : null}

      <div>
        <h1 className="text-2xl font-semibold text-foreground">Anomaly Thresholds</h1>
        <p className="text-sm text-muted-foreground">
          Review and update active threshold configurations by rule.
        </p>
      </div>

      {error ? (
        <p className="rounded-md border border-destructive/40 bg-destructive/10 px-3 py-2 text-sm text-destructive">
          {error}
        </p>
      ) : null}

      <section className="rounded-lg border border-border bg-card p-4">
        {loading ? (
          <div className="h-32 animate-pulse rounded-md border border-border bg-muted/30" />
        ) : null}

        {!loading && !sortedRows.length ? (
          <p className="rounded-md border border-border bg-muted/20 px-4 py-5 text-sm text-muted-foreground">
            No anomaly thresholds available.
          </p>
        ) : null}

        {!!sortedRows.length ? (
          <div className="overflow-x-auto rounded-md border border-border">
            <table aria-label="Anomaly thresholds" className="w-full min-w-[980px] text-sm">
              <thead>
                <tr className="bg-muted/30">
                  <th scope="col" className="px-3 py-2 text-left font-medium text-foreground">Rule Code</th>
                  <th scope="col" className="px-3 py-2 text-left font-medium text-foreground">
                    Current Threshold
                  </th>
                  <th scope="col" className="px-3 py-2 text-left font-medium text-foreground">Config</th>
                  <th scope="col" className="px-3 py-2 text-left font-medium text-foreground">Actions</th>
                </tr>
              </thead>
              <tbody>
                {sortedRows.map((row) => (
                  <tr key={row.rule_code} className="border-t border-border">
                    <td className="px-3 py-2 font-medium text-foreground">{row.rule_code}</td>
                    <td className="px-3 py-2 text-muted-foreground">{row.current_threshold}</td>
                    <td className="px-3 py-2">
                      <StructuredDataView
                        data={row.config ?? null}
                        emptyMessage="No configuration fields."
                        className="max-h-32 overflow-auto"
                        compact
                      />
                    </td>
                    <td className="px-3 py-2">
                      <Button
                        type="button"
                        size="sm"
                        variant="outline"
                        onClick={() => startEdit(row)}
                        disabled={savingRule === row.rule_code}
                      >
                        Edit
                      </Button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : null}
      </section>

      {editState ? (
        <Dialog open={Boolean(editState)} onClose={() => setEditState(null)} title="Edit threshold" size="lg">
          <div className="space-y-3">
            <p className="text-sm text-muted-foreground">Rule: {editState.ruleCode}</p>
            <label className="space-y-1 text-sm text-foreground" htmlFor="threshold-value">
              <span>Threshold Value</span>
              <Input
                id="threshold-value"
                value={editState.thresholdValue}
                onChange={(event) =>
                  setEditState((previous) =>
                    previous
                      ? { ...previous, thresholdValue: event.target.value }
                      : previous,
                  )
                }
              />
            </label>
            <label className="space-y-1 text-sm text-foreground" htmlFor="threshold-config">
              <span>Config (JSON)</span>
              <textarea
                id="threshold-config"
                className="min-h-40 w-full rounded-md border border-border bg-background px-3 py-2 font-mono text-xs text-foreground"
                value={editState.configText}
                onChange={(event) =>
                  setEditState((previous) =>
                    previous ? { ...previous, configText: event.target.value } : previous,
                  )
                }
              />
            </label>
          </div>
          <div className="mt-5 flex justify-end gap-2">
            <Button
              type="button"
              variant="outline"
              onClick={() => setEditState(null)}
              disabled={savingRule === editState.ruleCode}
            >
              Cancel
            </Button>
            <Button
              type="button"
              onClick={() => {
                void saveEdit()
              }}
              disabled={savingRule === editState.ruleCode}
            >
              {savingRule === editState.ruleCode ? (
                <>
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  Saving...
                </>
              ) : (
                "Save"
              )}
            </Button>
          </div>
        </Dialog>
      ) : null}
    </div>
  )
}
