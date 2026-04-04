"use client"

import { useMemo, useState } from "react"
import { useRouter } from "next/navigation"
import { Button } from "@/components/ui/button"
import { formatINR } from "@/lib/utils"
import {
  useConsolidationSummary,
  useOrgSetupSummaryForConsolidation,
  useRunConsolidation,
} from "@/hooks/useConsolidation"

const _today = new Date().toISOString().slice(0, 10)

export default function ConsolidationPage() {
  const router = useRouter()
  const orgSetupQuery = useOrgSetupSummaryForConsolidation()
  const runMutation = useRunConsolidation()

  const [asOfDate, setAsOfDate] = useState(_today)
  const [fromDate, setFromDate] = useState("")
  const [toDate, setToDate] = useState("")

  const orgGroupId = orgSetupQuery.data?.group?.id ?? ""

  const summaryParams = useMemo(
    () =>
      orgGroupId
        ? {
            orgGroupId,
            asOfDate,
            fromDate: fromDate || undefined,
            toDate: toDate || undefined,
          }
        : null,
    [orgGroupId, asOfDate, fromDate, toDate],
  )
  const summaryQuery = useConsolidationSummary(summaryParams)

  const runConsolidationNow = async () => {
    if (!orgGroupId) {
      return
    }
    const run = await runMutation.mutateAsync({
      org_group_id: orgGroupId,
      as_of_date: asOfDate,
      from_date: fromDate || undefined,
      to_date: toDate || undefined,
    })
    router.push(`/consolidation/runs/${run.run_id}`)
  }

  return (
    <div className="space-y-4">
      <section className="rounded-lg border border-border bg-card p-4">
        <h2 className="text-lg font-semibold text-foreground">
          Consolidation Engine
        </h2>
        <p className="mt-1 text-sm text-muted-foreground">
          Run group consolidation with ownership weighting and elimination
          summaries.
        </p>
        {!orgGroupId ? (
          <p className="mt-3 rounded-md border border-amber-500/30 bg-amber-500/10 px-3 py-2 text-sm text-amber-200">
            Org group is not configured yet. Complete Org Setup first.
          </p>
        ) : null}
      </section>

      <section className="rounded-lg border border-border bg-card p-4">
        <div className="grid gap-3 md:grid-cols-4">
          <label className="space-y-1 text-sm">
            <span className="text-foreground">As Of Date</span>
            <input
              className="w-full rounded-md border border-border bg-background px-3 py-2"
              type="date"
              value={asOfDate}
              onChange={(event) => setAsOfDate(event.target.value)}
            />
          </label>
          <label className="space-y-1 text-sm">
            <span className="text-foreground">From Date (Optional)</span>
            <input
              className="w-full rounded-md border border-border bg-background px-3 py-2"
              type="date"
              value={fromDate}
              onChange={(event) => setFromDate(event.target.value)}
            />
          </label>
          <label className="space-y-1 text-sm">
            <span className="text-foreground">To Date (Optional)</span>
            <input
              className="w-full rounded-md border border-border bg-background px-3 py-2"
              type="date"
              value={toDate}
              onChange={(event) => setToDate(event.target.value)}
            />
          </label>
          <div className="flex items-end gap-2">
            <Button
              type="button"
              variant="outline"
              disabled={summaryQuery.isFetching || !orgGroupId}
              onClick={() => void summaryQuery.refetch()}
            >
              {summaryQuery.isFetching ? "Refreshing..." : "Refresh Summary"}
            </Button>
            <Button
              type="button"
              disabled={runMutation.isPending || !orgGroupId}
              onClick={() => void runConsolidationNow()}
            >
              {runMutation.isPending ? "Running..." : "Run Consolidation"}
            </Button>
          </div>
        </div>
      </section>

      {summaryQuery.data ? (
        <section className="rounded-lg border border-border bg-card p-4">
          <h3 className="mb-3 text-lg font-semibold text-foreground">Summary</h3>
          <div className="grid gap-3 md:grid-cols-4">
            <SummaryCard
              label="Entities"
              value={String(summaryQuery.data.summary.entity_count)}
            />
            <SummaryCard
              label="Eliminations"
              value={String(summaryQuery.data.summary.elimination_count)}
            />
            <SummaryCard
              label="Total Eliminations"
              value={formatINR(summaryQuery.data.summary.total_eliminations)}
            />
            <SummaryCard
              label="Minority Interest"
              value={formatINR(
                summaryQuery.data.summary.minority_interest_placeholder,
              )}
            />
          </div>

          <h4 className="mt-4 text-sm font-semibold text-foreground">
            Elimination Summary
          </h4>
          <div className="mt-2 overflow-x-auto rounded-md border border-border">
            <table className="w-full text-sm">
              <thead className="bg-muted/30">
                <tr>
                  <th className="px-3 py-2 text-left">Type</th>
                  <th className="px-3 py-2 text-right">Amount</th>
                </tr>
              </thead>
              <tbody>
                {summaryQuery.data.elimination_summary.map((row) => (
                  <tr key={row.elimination_type} className="border-t border-border">
                    <td className="px-3 py-2">{row.elimination_type}</td>
                    <td className="px-3 py-2 text-right">
                      {formatINR(row.amount)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <h4 className="mt-4 text-sm font-semibold text-foreground">
            Entity Hierarchy
          </h4>
          <div className="mt-2 overflow-x-auto rounded-md border border-border">
            <table className="w-full text-sm">
              <thead className="bg-muted/30">
                <tr>
                  <th className="px-3 py-2 text-left">Entity</th>
                  <th className="px-3 py-2 text-left">Method</th>
                  <th className="px-3 py-2 text-right">Ownership %</th>
                  <th className="px-3 py-2 text-right">Factor</th>
                </tr>
              </thead>
              <tbody>
                {summaryQuery.data.hierarchy.rows.map((row) => (
                  <tr key={row.org_entity_id} className="border-t border-border">
                    <td className="px-3 py-2">{row.legal_name}</td>
                    <td className="px-3 py-2">{row.consolidation_method}</td>
                    <td className="px-3 py-2 text-right">
                      {row.ownership_pct}
                    </td>
                    <td className="px-3 py-2 text-right">
                      {row.ownership_factor}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      ) : null}

      {summaryQuery.isError ? (
        <p className="rounded-md border border-destructive/30 bg-destructive/10 px-4 py-3 text-sm text-destructive">
          Failed to load consolidation summary.
        </p>
      ) : null}
      {runMutation.isError ? (
        <p className="rounded-md border border-destructive/30 bg-destructive/10 px-4 py-3 text-sm text-destructive">
          Failed to start consolidation run.
        </p>
      ) : null}
    </div>
  )
}

function SummaryCard({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-md border border-border bg-background p-3">
      <p className="text-xs uppercase tracking-wide text-muted-foreground">
        {label}
      </p>
      <p className="mt-1 text-lg font-semibold text-foreground">{value}</p>
    </div>
  )
}
