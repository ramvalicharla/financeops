"use client"

import { useEffect, useState } from "react"
import { useSession } from "next-auth/react"
import { ModuleAccessNotice } from "@/components/common/ModuleAccessNotice"
import { Button } from "@/components/ui/button"
import { Dialog } from "@/components/ui/Dialog"
import { PayrollReconTable } from "@/components/reconciliation/PayrollReconTable"
import { useConnections, useSyncRuns } from "@/hooks/useSync"
import {
  usePayrollCostCentreDetail,
  usePayrollRecon,
} from "@/hooks/useReconciliation"
import { getAccessErrorMessage } from "@/lib/ui-access"
import { useUIStore } from "@/lib/store/ui"
import { formatINR, isZeroDecimal } from "@/lib/utils"
import type { PayrollCostCentre } from "@/types/reconciliation"

const varianceTone = (value: string) =>
  isZeroDecimal(value)
    ? "text-[hsl(var(--brand-success))]"
    : "text-[hsl(var(--brand-danger))]"

export default function PayrollReconciliationPage() {
  const { data: session } = useSession()
  const entityRoles = session?.user?.entity_roles ?? []
  const [selectedEntityId, setSelectedEntityId] = useState<string | null>(null)
  const { activePeriod, setActivePeriod } = useUIStore()
  const [selectedRunId, setSelectedRunId] = useState<string | null>(null)
  const [selectedConnectionId, setSelectedConnectionId] = useState<string | null>(null)
  const [selectedCostCentre, setSelectedCostCentre] =
    useState<PayrollCostCentre | null>(null)

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

  const reconQuery = usePayrollRecon(selectedEntityId, activePeriod, selectedRunId)
  const detailQuery = usePayrollCostCentreDetail(
    selectedEntityId,
    selectedCostCentre?.cost_centre_id ?? null,
    activePeriod,
  )
  const selectionErrorMessage =
    connectionsQuery.error?.message ?? syncRunsQuery.error?.message ?? null
  const accessErrorMessage = getAccessErrorMessage(
    connectionsQuery.error ?? syncRunsQuery.error ?? reconQuery.error ?? null,
    "Reconciliation",
  )

  if (accessErrorMessage) {
    return <ModuleAccessNotice message={accessErrorMessage} title="Module access" />
  }

  const filtersReady = Boolean(selectedEntityId && activePeriod && selectedRunId)
  const summary = reconQuery.data
  const employees =
    detailQuery.data?.employees ?? selectedCostCentre?.employees ?? []

  return (
    <div className="space-y-6">
      <section className="rounded-lg border border-border bg-card p-4">
        <div className="grid gap-3 md:grid-cols-3">
          <div className="space-y-1">
            <label className="text-sm text-foreground" htmlFor="payroll-entity">
              Entity
            </label>
            <select
              id="payroll-entity"
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
            <label className="text-sm text-foreground" htmlFor="payroll-period">
              Period
            </label>
            <input
              id="payroll-period"
              className="w-full rounded-md border border-border bg-background px-3 py-2 text-sm"
              type="month"
              value={activePeriod}
              onChange={(event) => setActivePeriod(event.target.value)}
            />
          </div>
          <div className="space-y-1">
            <label className="text-sm text-foreground" htmlFor="payroll-run">
              Sync Run
            </label>
            <select
              id="payroll-run"
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
        </div>
      </section>

      {!filtersReady ? (
        <p
          className={`rounded-md px-4 py-6 text-sm ${
            selectionErrorMessage
              ? "border border-destructive/30 bg-destructive/10 text-destructive"
              : "border border-border bg-card text-muted-foreground"
          }`}
        >
          {selectionErrorMessage ?? "Select entity, period and sync run to view results."}
        </p>
      ) : null}

      {filtersReady ? (
        <>
          {reconQuery.isError ? (
            <p className="rounded-md border border-destructive/30 bg-destructive/10 px-4 py-3 text-sm text-destructive">
              {reconQuery.error?.message ?? "Failed to load payroll reconciliation results."}
            </p>
          ) : null}
          <section className="grid gap-4 md:grid-cols-3">
            <article className="rounded-lg border border-border bg-card p-4">
              <p className="text-sm text-muted-foreground">Payroll Gross</p>
              <p className="mt-1 text-2xl font-semibold text-foreground">
                {formatINR(summary?.payroll_gross ?? "0")}
              </p>
            </article>
            <article className="rounded-lg border border-border bg-card p-4">
              <p className="text-sm text-muted-foreground">GL Gross</p>
              <p className="mt-1 text-2xl font-semibold text-foreground">
                {formatINR(summary?.gl_gross ?? "0")}
              </p>
            </article>
            <article className="rounded-lg border border-border bg-card p-4">
              <p className="text-sm text-muted-foreground">Gross Variance</p>
              <p className={`mt-1 text-2xl font-semibold ${varianceTone(summary?.gross_variance ?? "0")}`}>
                {formatINR(summary?.gross_variance ?? "0")}
              </p>
            </article>
            <article className="rounded-lg border border-border bg-card p-4">
              <p className="text-sm text-muted-foreground">Payroll Net</p>
              <p className="mt-1 text-2xl font-semibold text-foreground">
                {formatINR(summary?.payroll_net ?? "0")}
              </p>
            </article>
            <article className="rounded-lg border border-border bg-card p-4">
              <p className="text-sm text-muted-foreground">GL Net</p>
              <p className="mt-1 text-2xl font-semibold text-foreground">
                {formatINR(summary?.gl_net ?? "0")}
              </p>
            </article>
            <article className="rounded-lg border border-border bg-card p-4">
              <p className="text-sm text-muted-foreground">Net Variance</p>
              <p className={`mt-1 text-2xl font-semibold ${varianceTone(summary?.net_variance ?? "0")}`}>
                {formatINR(summary?.net_variance ?? "0")}
              </p>
            </article>
          </section>

          <section className="rounded-lg border border-border bg-card p-4">
            <h2 className="mb-3 text-lg font-semibold text-foreground">Cost Centres</h2>
            <div
              role="region"
              aria-label="Payroll reconciliation data"
              aria-busy={reconQuery.isLoading}
              aria-live="polite"
            >
              <PayrollReconTable
                costCentres={summary?.cost_centres ?? []}
                onRowClick={(costCentre) => setSelectedCostCentre(costCentre)}
              />
            </div>
          </section>
        </>
      ) : null}

      {selectedCostCentre ? (
        <Dialog open={Boolean(selectedCostCentre)} onClose={() => setSelectedCostCentre(null)} title="Payroll detail" size="lg">
          <div className="mb-4">
            <h3 className="text-lg font-semibold text-foreground">
              {selectedCostCentre.cost_centre_name}
            </h3>
            <p className="text-sm text-muted-foreground">
              Employee breakdown
            </p>
          </div>
          <div className="overflow-x-auto rounded-md border border-border">
            <table className="w-full min-w-[960px] text-sm">
              <thead>
                <tr className="bg-muted/30">
                  <th className="px-3 py-2 text-left font-medium text-foreground">
                    Employee
                  </th>
                  <th className="px-3 py-2 text-right font-medium text-foreground">
                    Gross Pay
                  </th>
                  <th className="px-3 py-2 text-right font-medium text-foreground">
                    Net Pay
                  </th>
                  <th className="px-3 py-2 text-right font-medium text-foreground">
                    Deductions
                  </th>
                  <th className="px-3 py-2 text-right font-medium text-foreground">
                    GL Posting
                  </th>
                  <th className="px-3 py-2 text-right font-medium text-foreground">
                    Variance
                  </th>
                  <th className="px-3 py-2 text-left font-medium text-foreground">
                    Status
                  </th>
                </tr>
              </thead>
              <tbody>
                {employees.map((employee) => {
                  const matched = isZeroDecimal(employee.variance)
                  return (
                    <tr key={employee.employee_id} className="border-t border-border">
                      <td className="px-3 py-2 text-muted-foreground">
                        {employee.employee_name}
                      </td>
                      <td className="px-3 py-2 text-right text-muted-foreground">
                        {formatINR(employee.gross_pay)}
                      </td>
                      <td className="px-3 py-2 text-right text-muted-foreground">
                        {formatINR(employee.net_pay)}
                      </td>
                      <td className="px-3 py-2 text-right text-muted-foreground">
                        {formatINR(employee.deductions)}
                      </td>
                      <td className="px-3 py-2 text-right text-muted-foreground">
                        {formatINR(employee.gl_posting)}
                      </td>
                      <td
                        className={`px-3 py-2 text-right ${
                          matched
                            ? "text-[hsl(var(--brand-success))]"
                            : "text-[hsl(var(--brand-danger))]"
                        }`}
                      >
                        {formatINR(employee.variance)}
                      </td>
                      <td className="px-3 py-2">
                        <span
                          className={`inline-flex rounded-full px-2 py-1 text-xs font-medium ${
                            matched
                              ? "bg-[hsl(var(--brand-success)/0.2)] text-[hsl(var(--brand-success))]"
                              : "bg-[hsl(var(--brand-danger)/0.2)] text-[hsl(var(--brand-danger))]"
                          }`}
                        >
                          {matched ? "Matched" : "Variance"}
                        </span>
                      </td>
                    </tr>
                  )
                })}
                {!employees.length ? (
                  <tr>
                    <td
                      colSpan={7}
                      className="px-3 py-4 text-center text-muted-foreground"
                    >
                      No employee breakdown available.
                    </td>
                  </tr>
                ) : null}
              </tbody>
            </table>
          </div>
        </Dialog>
      ) : null}
    </div>
  )
}
