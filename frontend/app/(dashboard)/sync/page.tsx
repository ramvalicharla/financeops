"use client"

import { useEffect, useMemo, useState } from "react"
import { formatDistanceToNowStrict } from "date-fns"
import { useRouter, useSearchParams } from "next/navigation"
import { Button } from "@/components/ui/button"
import { SyncRunTable } from "@/components/sync/SyncRunTable"
import { SyncStatusBadge } from "@/components/sync/SyncStatusBadge"
import {
  useAllDatasetTypes,
  useApprovePublish,
  useConnections,
  useDriftReport,
  useSyncRuns,
  useTriggerSync,
} from "@/hooks/useSync"
import { cn } from "@/lib/utils"
import type { SyncRun, ValidationResult } from "@/types/sync"
import { useUIStore } from "@/lib/store/ui"

const validationCategories = [
  "REQUIRED_FIELD_PRESENCE",
  "DUPLICATE_SYNC",
  "CURRENCY_CONSISTENCY",
  "ENTITY_SCOPE",
  "PERIOD_CONSISTENCY",
  "BALANCE_CHECK",
  "SNAPSHOT_INTEGRITY",
  "DELTA_BOUNDARY",
  "CAPABILITY_MISMATCH",
  "MAPPING_COMPLETENESS",
  "AGEING_BUCKET",
  "REGISTER_LINE",
  "BANK_BALANCE",
  "BANK_MULTICURRENCY",
  "INVENTORY_VALUE",
  "MASTER_DATA_REFERENTIAL",
  "PII_CONSENT",
  "IRN_FORMAT",
  "GSTR_PERIOD",
  "BACKDATED_MODIFICATION",
]

const driftBadgeClass = (severity: "NONE" | "MINOR" | "SIGNIFICANT" | "CRITICAL" | null) => {
  if (severity === "CRITICAL") {
    return "bg-[hsl(var(--brand-danger)/0.2)] text-[hsl(var(--brand-danger))]"
  }
  if (severity === "SIGNIFICANT") {
    return "bg-[hsl(var(--brand-warning)/0.2)] text-[hsl(var(--brand-warning))]"
  }
  if (severity === "MINOR") {
    return "bg-[hsl(var(--brand-success)/0.2)] text-[hsl(var(--brand-success))]"
  }
  return "bg-muted text-muted-foreground"
}

const getRelativeTime = (value: string | null): string =>
  value ? formatDistanceToNowStrict(new Date(value), { addSuffix: true }) : "Never"

const mergeValidationResults = (
  results: ValidationResult[],
): Array<ValidationResult & { category: string }> =>
  validationCategories.map((category) => {
    const found = results.find((result) => result.category === category)
    return (
      found ?? {
        category,
        passed: false,
        message: "Not returned by API.",
      }
    )
  })

export default function SyncPage() {
  const router = useRouter()
  const searchParams = useSearchParams()
  const [selectedConnectionId, setSelectedConnectionId] = useState<string | null>(
    searchParams?.get("connection_id") ?? null,
  )
  const [validationRun, setValidationRun] = useState<SyncRun | null>(null)
  const [driftRun, setDriftRun] = useState<SyncRun | null>(null)
  const [criticalAcknowledged, setCriticalAcknowledged] = useState(false)
  const setNotificationItems = useUIStore((state) => state.setNotificationItems)

  const connectionsQuery = useConnections()
  const syncRunsQuery = useSyncRuns(selectedConnectionId)
  const triggerSyncMutation = useTriggerSync()
  const approvePublishMutation = useApprovePublish()
  const allDatasetTypes = useAllDatasetTypes()
  const driftQuery = useDriftReport(driftRun?.id ?? null)

  useEffect(() => {
    if (!connectionsQuery.data?.length) {
      return
    }
    if (!selectedConnectionId) {
      setSelectedConnectionId(connectionsQuery.data[0]?.id ?? null)
    }
  }, [connectionsQuery.data, selectedConnectionId])

  const selectedConnection = useMemo(
    () =>
      connectionsQuery.data?.find(
        (connection) => connection.id === selectedConnectionId,
      ) ?? null,
    [connectionsQuery.data, selectedConnectionId],
  )

  const validationRows = useMemo(
    () => mergeValidationResults(validationRun?.validation_results ?? []),
    [validationRun],
  )
  const failedValidationCount = validationRows.filter((row) => !row.passed).length

  useEffect(() => {
    const runs = syncRunsQuery.data ?? []
    const pendingApprovalItems = runs
      .filter((run) => run.status === "COMPLETED" && !run.publish_event_id)
      .map((run) => ({
        id: `publish-${run.id}`,
        label: `Publish approval pending: ${run.dataset_type.replaceAll("_", " ")}`,
        href: "/sync",
      }))
    const criticalDriftItems = runs
      .filter((run) => run.drift_severity === "CRITICAL")
      .map((run) => ({
        id: `drift-${run.id}`,
        label: `Critical drift: ${run.dataset_type.replaceAll("_", " ")}`,
        href: "/sync",
      }))
    setNotificationItems([...pendingApprovalItems, ...criticalDriftItems])
  }, [setNotificationItems, syncRunsQuery.data])

  return (
    <div className="grid gap-6 lg:grid-cols-[320px_1fr]">
      <section className="rounded-lg border border-border bg-card p-4">
        <div className="mb-4 flex items-center justify-between">
          <h2 className="text-lg font-semibold text-foreground">Connected Sources</h2>
          <Button size="sm" onClick={() => router.push("/sync/connect")} type="button">
            Add Source
          </Button>
        </div>

        {connectionsQuery.isLoading ? (
          <div className="space-y-2">
            {Array.from({ length: 4 }).map((_, index) => (
              <div
                key={`connection-skeleton-${index}`}
                className="h-20 animate-pulse rounded-md border border-border bg-muted/30"
              />
            ))}
          </div>
        ) : null}

        {!connectionsQuery.isLoading && !connectionsQuery.data?.length ? (
          <p className="rounded-md border border-border bg-muted/20 px-3 py-4 text-sm text-muted-foreground">
            No sources connected. Add your first source.
          </p>
        ) : null}

        {connectionsQuery.isError ? (
          <p className="rounded-md border border-destructive/30 bg-destructive/10 px-3 py-4 text-sm text-destructive">
            Failed to load connected sources.
          </p>
        ) : null}

        <div className="space-y-2">
          {connectionsQuery.data?.map((connection) => (
            <button
              key={connection.id}
              className={cn(
                "w-full rounded-md border px-3 py-3 text-left transition",
                selectedConnectionId === connection.id
                  ? "border-[hsl(var(--brand-primary))] bg-[hsl(var(--brand-primary)/0.12)]"
                  : "border-border hover:border-[hsl(var(--brand-primary)/0.5)]",
              )}
              onClick={() => setSelectedConnectionId(connection.id)}
              type="button"
            >
              <p className="font-medium text-foreground">{connection.display_name}</p>
              <p className="mt-1 text-xs text-muted-foreground">
                Last sync {getRelativeTime(connection.last_sync_at)}
              </p>
              <div className="mt-2">
                {connection.last_sync_status ? (
                  <SyncStatusBadge status={connection.last_sync_status} />
                ) : (
                  <span className="inline-flex rounded-full bg-muted px-2 py-1 text-xs text-muted-foreground">
                    No runs yet
                  </span>
                )}
              </div>
            </button>
          ))}
        </div>
      </section>

      <section className="rounded-lg border border-border bg-card p-4">
        <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
          <h2 className="text-lg font-semibold text-foreground">Sync History</h2>
          <Button
            disabled={!selectedConnectionId || triggerSyncMutation.isPending}
            onClick={() => {
              if (!selectedConnectionId) {
                return
              }
              void triggerSyncMutation.mutateAsync({
                connectionId: selectedConnectionId,
                datasetTypes: allDatasetTypes,
              })
            }}
            type="button"
          >
            {triggerSyncMutation.isPending ? "Syncing..." : "Sync Now"}
          </Button>
        </div>

        {!selectedConnectionId ? (
          <p className="rounded-md border border-border bg-muted/20 px-3 py-4 text-sm text-muted-foreground">
            Select a source to view sync history.
          </p>
        ) : null}

        {selectedConnectionId && syncRunsQuery.isLoading ? (
          <div className="h-40 animate-pulse rounded-md border border-border bg-muted/20" />
        ) : null}

        {selectedConnectionId && !syncRunsQuery.isLoading && !syncRunsQuery.data?.length ? (
          <p className="rounded-md border border-border bg-muted/20 px-3 py-4 text-sm text-muted-foreground">
            No sync runs yet. Click Sync Now to start.
          </p>
        ) : null}

        {selectedConnectionId && syncRunsQuery.isError ? (
          <p className="rounded-md border border-destructive/30 bg-destructive/10 px-3 py-4 text-sm text-destructive">
            Failed to load sync run history.
          </p>
        ) : null}

        {selectedConnectionId && syncRunsQuery.data?.length ? (
          <SyncRunTable
            isApproving={approvePublishMutation.isPending}
            onApprovePublish={(run) => {
              const publishId = run.publish_event_id ?? run.id
              void approvePublishMutation.mutateAsync(publishId)
            }}
            onValidationReport={(run) => setValidationRun(run)}
            onViewDrift={(run) => {
              setDriftRun(run)
              setCriticalAcknowledged(false)
            }}
            runs={syncRunsQuery.data}
          />
        ) : null}
      </section>

      {validationRun ? (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4">
          <div className="max-h-[85vh] w-full max-w-3xl overflow-auto rounded-lg border border-border bg-card p-5">
            <div className="mb-3 flex items-center justify-between">
              <h3 className="text-lg font-semibold text-foreground">Validation Details</h3>
              <Button
                onClick={() => setValidationRun(null)}
                size="sm"
                type="button"
                variant="outline"
              >
                Close
              </Button>
            </div>
            <p className="mb-3 text-sm">
              {failedValidationCount === 0 ? (
                <span className="text-[hsl(var(--brand-success))]">All checks passed.</span>
              ) : (
                <span className="text-[hsl(var(--brand-danger))]">
                  {failedValidationCount} checks failed.
                </span>
              )}
            </p>
            <div className="overflow-x-auto rounded-md border border-border">
              <table className="w-full min-w-[720px] text-sm">
                <thead>
                  <tr className="bg-muted/30">
                    <th className="px-3 py-2 text-left font-medium text-foreground">
                      Category
                    </th>
                    <th className="px-3 py-2 text-left font-medium text-foreground">
                      Result
                    </th>
                    <th className="px-3 py-2 text-left font-medium text-foreground">
                      Message
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {validationRows.map((row) => (
                    <tr key={row.category} className="border-t border-border">
                      <td className="px-3 py-2 text-muted-foreground">{row.category}</td>
                      <td className="px-3 py-2">
                        <span
                          className={cn(
                            "inline-flex rounded-full px-2 py-1 text-xs font-medium",
                            row.passed
                              ? "bg-[hsl(var(--brand-success)/0.2)] text-[hsl(var(--brand-success))]"
                              : "bg-[hsl(var(--brand-danger)/0.2)] text-[hsl(var(--brand-danger))]",
                          )}
                        >
                          {row.passed ? "PASS" : "FAIL"}
                        </span>
                      </td>
                      <td className="px-3 py-2 text-muted-foreground">
                        {row.message ?? "—"}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      ) : null}

      {driftRun ? (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4">
          <div className="max-h-[85vh] w-full max-w-3xl overflow-auto rounded-lg border border-border bg-card p-5">
            <div className="mb-3 flex items-center justify-between">
              <h3 className="text-lg font-semibold text-foreground">Drift Report</h3>
              <Button
                onClick={() => setDriftRun(null)}
                size="sm"
                type="button"
                variant="outline"
              >
                Close
              </Button>
            </div>
            <div className="mb-3 flex items-center justify-between">
              <span
                className={cn(
                  "inline-flex rounded-full px-2 py-1 text-xs font-medium",
                  driftBadgeClass(driftQuery.data?.severity ?? driftRun.drift_severity),
                )}
              >
                {(driftQuery.data?.severity ?? driftRun.drift_severity ?? "NONE").toString()}
              </span>
              {driftQuery.data?.severity === "CRITICAL" ? (
                <Button
                  size="sm"
                  type="button"
                  variant="secondary"
                  onClick={() => setCriticalAcknowledged(true)}
                >
                  Acknowledge
                </Button>
              ) : null}
            </div>
            {criticalAcknowledged ? (
              <p className="mb-3 text-sm text-[hsl(var(--brand-warning))]">
                Critical drift acknowledged for this review session.
              </p>
            ) : null}
            <div className="overflow-x-auto rounded-md border border-border">
              <table className="w-full min-w-[720px] text-sm">
                <thead>
                  <tr className="bg-muted/30">
                    <th className="px-3 py-2 text-left font-medium text-foreground">
                      Field
                    </th>
                    <th className="px-3 py-2 text-left font-medium text-foreground">
                      Previous Value
                    </th>
                    <th className="px-3 py-2 text-left font-medium text-foreground">
                      Current Value
                    </th>
                    <th className="px-3 py-2 text-left font-medium text-foreground">
                      Change %
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {(driftQuery.data?.changes ?? []).map((change) => (
                    <tr key={`${change.field}-${change.previous_value}`} className="border-t border-border">
                      <td className="px-3 py-2 text-muted-foreground">{change.field}</td>
                      <td className="px-3 py-2 text-muted-foreground">
                        {change.previous_value}
                      </td>
                      <td className="px-3 py-2 text-muted-foreground">
                        {change.current_value}
                      </td>
                      <td className="px-3 py-2 text-muted-foreground">
                        {change.change_pct.toFixed(2)}%
                      </td>
                    </tr>
                  ))}
                  {!driftQuery.data?.changes?.length ? (
                    <tr>
                      <td
                        className="px-3 py-3 text-center text-muted-foreground"
                        colSpan={4}
                      >
                        No drift changes available.
                      </td>
                    </tr>
                  ) : null}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      ) : null}
    </div>
  )
}
