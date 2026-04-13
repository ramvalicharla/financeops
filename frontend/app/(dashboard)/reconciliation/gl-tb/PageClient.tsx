"use client"

import { useEffect, useMemo, useState } from "react"
import { useSession } from "next-auth/react"
import { ModuleAccessNotice } from "@/components/common/ModuleAccessNotice"
import { EmptyState } from "@/components/ui/EmptyState"
import { Button } from "@/components/ui/button"
import { Sheet } from "@/components/ui/Sheet"
import { GLTBTable } from "@/components/reconciliation/GLTBTable"
import { VarianceBadge } from "@/components/reconciliation/VarianceBadge"
import { useConnections, useSyncRuns } from "@/hooks/useSync"
import {
  useExportGLTB,
  useGLTBAccountEntries,
  useGLTBResult,
} from "@/hooks/useReconciliation"
import { getAccessErrorMessage } from "@/lib/ui-access"
import { useUIStore } from "@/lib/store/ui"
import { formatINR, isZeroDecimal } from "@/lib/utils"
import type { GLTBAccount } from "@/types/reconciliation"

type StatusFilter = "ALL" | "MATCHED" | "VARIANCE" | "MISSING_GL" | "MISSING_TB"

export default function GLTBReconciliationPage() {
  const { data: session } = useSession()
  const entityRoles = session?.user?.entity_roles ?? []
  const [selectedEntityId, setSelectedEntityId] = useState<string | null>(null)
  const { activePeriod, setActivePeriod } = useUIStore()
  const [selectedRunId, setSelectedRunId] = useState<string | null>(null)
  const [selectedConnectionId, setSelectedConnectionId] = useState<string | null>(null)
  const [statusFilter, setStatusFilter] = useState<StatusFilter>("ALL")
  const [selectedAccount, setSelectedAccount] = useState<GLTBAccount | null>(null)

  const connectionsQuery = useConnections()
  const syncRunsQuery = useSyncRuns(selectedConnectionId)

  useEffect(() => {
    if (!selectedEntityId && entityRoles.length) {
      setSelectedEntityId(entityRoles[0]?.entity_id ?? null)
    }
  }, [entityRoles, selectedEntityId])

  useEffect(() => {
    if (!selectedConnectionId && connectionsQuery.data?.length) {
      setSelectedConnectionId(connectionsQuery.data[0]?.id ?? null)
    }
  }, [connectionsQuery.data, selectedConnectionId])

  useEffect(() => {
    if (!selectedRunId && syncRunsQuery.data?.length) {
      setSelectedRunId(syncRunsQuery.data[0]?.id ?? null)
    }
  }, [selectedRunId, syncRunsQuery.data])

  const resultQuery = useGLTBResult(selectedEntityId, activePeriod, selectedRunId)
  const entriesQuery = useGLTBAccountEntries(
    selectedEntityId,
    selectedAccount?.account_code ?? null,
    activePeriod,
  )
  const exportMutation = useExportGLTB()
  const selectionErrorMessage =
    connectionsQuery.error?.message ?? syncRunsQuery.error?.message ?? null
  const accessErrorMessage = getAccessErrorMessage(
    connectionsQuery.error ?? syncRunsQuery.error ?? resultQuery.error ?? null,
    "Reconciliation",
  )

  const filteredAccounts = useMemo(() => {
    const accounts = resultQuery.data?.accounts ?? []
    if (statusFilter === "ALL") {
      return accounts
    }
    return accounts.filter((account) => account.status === statusFilter)
  }, [resultQuery.data?.accounts, statusFilter])

  const filtersReady = Boolean(selectedEntityId && activePeriod && selectedRunId)
  const summary = resultQuery.data

  if (accessErrorMessage) {
    return <ModuleAccessNotice message={accessErrorMessage} title="Module access" />
  }

  return (
    <div className="space-y-6">
      <section className="rounded-lg border border-border bg-card p-4">
        <div className="grid gap-3 md:grid-cols-[1fr_1fr_1fr_auto]">
          <div className="space-y-1">
            <label className="text-sm text-foreground" htmlFor="gltb-entity">
              Entity
            </label>
            <select
              id="gltb-entity"
              className="w-full rounded-md border border-border bg-background px-3 py-2 text-sm"
              value={selectedEntityId ?? ""}
              onChange={(event) => setSelectedEntityId(event.target.value || null)}
            >
              <option value="">Select entity</option>
              {entityRoles.map((entityRole) => (
                <option key={entityRole.entity_id} value={entityRole.entity_id}>
                  {entityRole.entity_name}
                </option>
              ))}
            </select>
          </div>
          <div className="space-y-1">
            <label className="text-sm text-foreground" htmlFor="gltb-period">
              Period
            </label>
            <input
              id="gltb-period"
              className="w-full rounded-md border border-border bg-background px-3 py-2 text-sm"
              type="month"
              value={activePeriod}
              onChange={(event) => setActivePeriod(event.target.value)}
            />
          </div>
          <div className="space-y-1">
            <label className="text-sm text-foreground" htmlFor="gltb-run">
              Sync Run
            </label>
            <select
              id="gltb-run"
              className="w-full rounded-md border border-border bg-background px-3 py-2 text-sm"
              value={selectedRunId ?? ""}
              onChange={(event) => setSelectedRunId(event.target.value || null)}
            >
              <option value="">Select run</option>
              {syncRunsQuery.data?.map((run) => (
                <option key={run.id} value={run.id}>
                  {run.dataset_type.replaceAll("_", " ")} - {run.status} -{" "}
                  {new Date(run.started_at).toLocaleString()}
                </option>
              ))}
            </select>
          </div>
          <div className="flex items-end justify-end">
            <Button
              type="button"
              disabled={!filtersReady || exportMutation.isPending}
              onClick={() => {
                if (!selectedEntityId || !selectedRunId) {
                  return
                }
                void exportMutation.mutateAsync({
                  entityId: selectedEntityId,
                  period: activePeriod,
                  runId: selectedRunId,
                })
              }}
            >
              {exportMutation.isPending ? "Exporting..." : "Export CSV"}
            </Button>
          </div>
        </div>
      </section>

      {!filtersReady && selectionErrorMessage ? (
        <p className="rounded-md border border-destructive/30 bg-destructive/10 px-4 py-6 text-sm text-destructive">
          {selectionErrorMessage}
        </p>
      ) : null}

      {!filtersReady && !selectionErrorMessage ? (
        <EmptyState
          title="No entries to show"
          description="Select a period and account range to load GL/TB data"
        />
      ) : null}

      {filtersReady ? (
        <>
          {resultQuery.isError ? (
            <p className="rounded-md border border-destructive/30 bg-destructive/10 px-4 py-3 text-sm text-destructive">
              {resultQuery.error?.message ?? "Failed to load GL/TB reconciliation results."}
            </p>
          ) : null}
          <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
            <article className="rounded-lg border border-border bg-card p-4">
              <p className="text-sm text-muted-foreground">Total Accounts</p>
              <p className="mt-1 text-2xl font-semibold text-foreground">
                {summary?.total_accounts ?? 0}
              </p>
            </article>
            <article className="rounded-lg border border-border bg-card p-4">
              <p className="text-sm text-muted-foreground">Matched</p>
              <p
                className={`mt-1 text-2xl font-semibold ${
                  summary &&
                  summary.matched_accounts === summary.total_accounts
                    ? "text-[hsl(var(--brand-success))]"
                    : "text-[hsl(var(--brand-warning))]"
                }`}
              >
                {summary?.matched_accounts ?? 0}
              </p>
            </article>
            <article className="rounded-lg border border-border bg-card p-4">
              <p className="text-sm text-muted-foreground">Variance Accounts</p>
              <p
                className={`mt-1 text-2xl font-semibold ${
                  summary && summary.variance_accounts > 0
                    ? "text-[hsl(var(--brand-danger))]"
                    : "text-[hsl(var(--brand-success))]"
                }`}
              >
                {summary?.variance_accounts ?? 0}
              </p>
            </article>
            <article className="rounded-lg border border-border bg-card p-4">
              <p className="text-sm text-muted-foreground">Total Variance (INR)</p>
              <p
                className={`mt-1 text-2xl font-semibold ${
                  summary && !isZeroDecimal(summary.total_variance)
                    ? "text-[hsl(var(--brand-danger))]"
                    : "text-[hsl(var(--brand-success))]"
                }`}
              >
                {summary ? formatINR(summary.total_variance) : formatINR("0")}
              </p>
            </article>
          </section>

          <section className="space-y-3 rounded-lg border border-border bg-card p-4">
            <div className="flex items-center justify-between">
              <h2 className="text-lg font-semibold text-foreground">
                GL/TB Accounts
              </h2>
              <div className="flex items-center gap-2">
                <label className="text-sm text-muted-foreground" htmlFor="gltb-status">
                  Status
                </label>
                <select
                  id="gltb-status"
                  className="rounded-md border border-border bg-background px-2 py-1 text-sm"
                  value={statusFilter}
                  onChange={(event) => setStatusFilter(event.target.value as StatusFilter)}
                >
                  <option value="ALL">All</option>
                  <option value="MATCHED">Matched</option>
                  <option value="VARIANCE">Variance</option>
                  <option value="MISSING_GL">Missing in GL</option>
                  <option value="MISSING_TB">Missing in TB</option>
                </select>
              </div>
            </div>
            <div
              role="region"
              aria-label="GL/TB reconciliation data"
              aria-busy={resultQuery.isLoading}
              aria-live="polite"
            >
              <GLTBTable
                accounts={filteredAccounts}
                onRowClick={(account) => setSelectedAccount(account)}
              />
            </div>
          </section>
        </>
      ) : null}

      {selectedAccount ? (
        <Sheet open={Boolean(selectedAccount)} onClose={() => setSelectedAccount(null)} title="Transaction detail" width="max-w-2xl">
          <div className="mb-4">
            <p className="text-sm text-muted-foreground">
              {selectedAccount.account_code}
            </p>
          </div>
          <div className="mb-3">
            <VarianceBadge status={selectedAccount.status} />
          </div>
          <div className="overflow-x-auto w-full rounded-md border border-border">
              <table className="w-full min-w-[780px] text-sm">
                <thead>
                  <tr className="bg-muted/30">
                    <th className="px-3 py-2 text-left font-medium text-foreground">
                      Date
                    </th>
                    <th className="px-3 py-2 text-left font-medium text-foreground">
                      Description
                    </th>
                    <th className="px-3 py-2 text-left font-medium text-foreground">
                      Reference
                    </th>
                    <th className="px-3 py-2 text-right font-medium text-foreground">
                      Debit
                    </th>
                    <th className="px-3 py-2 text-right font-medium text-foreground">
                      Credit
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {(entriesQuery.data ?? selectedAccount.journal_entries ?? []).map(
                    (entry) => (
                      <tr key={entry.entry_id} className="border-t border-border">
                        <td className="px-3 py-2 text-muted-foreground">
                          {new Date(entry.date).toLocaleDateString()}
                        </td>
                        <td className="px-3 py-2 text-muted-foreground">
                          {entry.description}
                        </td>
                        <td className="px-3 py-2 text-muted-foreground">
                          {entry.reference ?? "—"}
                        </td>
                        <td className="px-3 py-2 text-right text-muted-foreground">
                          {formatINR(entry.debit)}
                        </td>
                        <td className="px-3 py-2 text-right text-muted-foreground">
                          {formatINR(entry.credit)}
                        </td>
                      </tr>
                    ),
                  )}
                  {!(entriesQuery.data ?? selectedAccount.journal_entries ?? []).length ? (
                    <tr>
                      <td
                        colSpan={5}
                        className="px-3 py-4 text-center text-muted-foreground"
                      >
                        No journal entries available for this account.
                      </td>
                    </tr>
                  ) : null}
                </tbody>
              </table>
          </div>
        </Sheet>
      ) : null}
    </div>
  )
}
