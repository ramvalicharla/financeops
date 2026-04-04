"use client"

import { useMemo } from "react"
import Link from "next/link"
import { useParams } from "next/navigation"
import { Button } from "@/components/ui/button"
import { formatINR } from "@/lib/utils"
import {
  useConsolidationRun,
  useConsolidationRunStatements,
} from "@/hooks/useConsolidation"

export default function ConsolidationRunDetailsPage() {
  const params = useParams<{ id: string }>()
  const runId = params?.id ?? null
  const runQuery = useConsolidationRun(runId)
  const statementsQuery = useConsolidationRunStatements(runId)

  const trialBalanceRows = useMemo(
    () => statementsQuery.data?.statements?.trial_balance?.rows ?? [],
    [statementsQuery.data],
  )

  return (
    <div className="space-y-4">
      <section className="rounded-lg border border-border bg-card p-4">
        <div className="flex items-center justify-between gap-3">
          <div>
            <h2 className="text-lg font-semibold text-foreground">
              Consolidation Run
            </h2>
            <p className="text-sm text-muted-foreground">{runId}</p>
          </div>
          <Link href="/consolidation">
            <Button type="button" variant="outline">
              Back
            </Button>
          </Link>
        </div>
      </section>

      {runQuery.data ? (
        <section className="rounded-lg border border-border bg-card p-4">
          <div className="grid gap-3 md:grid-cols-4">
            <DataCard label="Status" value={runQuery.data.status} />
            <DataCard
              label="Event Seq"
              value={String(runQuery.data.event_seq)}
            />
            <DataCard
              label="Workflow ID"
              value={runQuery.data.workflow_id.slice(0, 20)}
            />
            <DataCard
              label="Eliminations"
              value={String(runQuery.data.summary?.elimination_count ?? 0)}
            />
          </div>
        </section>
      ) : null}

      {statementsQuery.data ? (
        <>
          <section className="rounded-lg border border-border bg-card p-4">
            <h3 className="mb-3 text-lg font-semibold text-foreground">
              Trial Balance
            </h3>
            <div className="mb-3 grid gap-3 md:grid-cols-2">
              <DataCard
                label="Total Debit"
                value={formatINR(
                  statementsQuery.data.statements.trial_balance.total_debit,
                )}
              />
              <DataCard
                label="Total Credit"
                value={formatINR(
                  statementsQuery.data.statements.trial_balance.total_credit,
                )}
              />
            </div>
            <div className="max-h-[420px] overflow-auto rounded-md border border-border">
              <table aria-label="Consolidation run details" className="w-full text-sm">
                <thead className="sticky top-0 bg-muted/30">
                  <tr>
                    <th scope="col" className="px-3 py-2 text-left">Code</th>
                    <th scope="col" className="px-3 py-2 text-left">Account</th>
                    <th scope="col" className="px-3 py-2 text-right">Debit</th>
                    <th scope="col" className="px-3 py-2 text-right">Credit</th>
                    <th scope="col" className="px-3 py-2 text-right">Balance</th>
                  </tr>
                </thead>
                <tbody>
                  {trialBalanceRows.map((row) => (
                    <tr key={row.account_code} className="border-t border-border">
                      <td className="px-3 py-2">{row.account_code}</td>
                      <td className="px-3 py-2">{row.account_name}</td>
                      <td className="px-3 py-2 text-right">
                        {formatINR(row.debit_sum)}
                      </td>
                      <td className="px-3 py-2 text-right">
                        {formatINR(row.credit_sum)}
                      </td>
                      <td className="px-3 py-2 text-right">
                        {formatINR(row.balance)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>

          <section className="rounded-lg border border-border bg-card p-4">
            <h3 className="mb-3 text-lg font-semibold text-foreground">
              Elimination Summary
            </h3>
            <div className="overflow-x-auto rounded-md border border-border">
              <table aria-label="Consolidation run details" className="w-full text-sm">
                <thead className="bg-muted/30">
                  <tr>
                    <th scope="col" className="px-3 py-2 text-left">Type</th>
                    <th scope="col" className="px-3 py-2 text-right">Amount</th>
                  </tr>
                </thead>
                <tbody>
                  {statementsQuery.data.elimination_summary.map((row) => (
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
          </section>
        </>
      ) : null}

      {runQuery.isError || statementsQuery.isError ? (
        <p className="rounded-md border border-destructive/30 bg-destructive/10 px-4 py-3 text-sm text-destructive">
          Failed to load consolidation run details.
        </p>
      ) : null}
    </div>
  )
}

function DataCard({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-md border border-border bg-background p-3">
      <p className="text-xs uppercase tracking-wide text-muted-foreground">
        {label}
      </p>
      <p className="mt-1 text-base font-semibold text-foreground">{value}</p>
    </div>
  )
}
